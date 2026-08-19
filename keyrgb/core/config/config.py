"""KeyRGB Config implementation."""

from __future__ import annotations

# @quality-exception file-size-analysis: Config facade class; domain accessors live in sibling modules
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Literal, overload

from . import defaults as _defaults, file_storage as _file_storage, paths as _paths, perkey_colors as _perkey_colors
from ._app_accessors import AppConfigAccessors
from ._lighting import (
    _coercion as _lighting_coercion,
    _effect_speed_overrides as _effect_speed_boundary,
    _lighting_accessors,
)
from ._power_accessors import PowerConfigAccessors
from ._scheduler_accessors import SchedulerConfigAccessors
from ._settings_view import ConfigSettingsView
from .document import ConfigDocument
from .domains import ConfigDomain

logger = logging.getLogger(__name__)


class ConfigPersistenceError(OSError):
    """Raised when configuration changes cannot be persisted to disk.

    Ordinary property setters and ``batch_update()`` both surface this error.
    Failed ordinary saves restore in-memory settings to the last persisted
    snapshot so callers do not keep a silently divergent dirty view.
    """


def _normalized_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


class Config(
    AppConfigAccessors,
    SchedulerConfigAccessors,
    PowerConfigAccessors,
    _lighting_accessors.LightingConfigAccessors,
):
    """Configuration manager for KeyRGB.

    Public property facades stay stable. Internally, settings live in a
    ``ConfigDocument`` whose keys are partitioned by ``ConfigDomain`` so lighting,
    power, idle/display, scheduler, layout, secondary, and app concerns are not
    one undifferentiated bag. On-disk JSON remains a flat mapping.
    """

    # Kept for backward compatibility with existing callers.
    CONFIG_DIR = _paths.config_dir()
    CONFIG_FILE = _paths.config_file_path()

    DEFAULTS = _defaults.DEFAULTS

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:
        """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""
        return _perkey_colors.serialize_per_key_colors(color_map)

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:
        """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""
        return _perkey_colors.deserialize_per_key_colors(data)

    def __init__(self) -> None:
        # Recompute at runtime so test harnesses can set env vars in conftest.
        self.CONFIG_DIR = _paths.config_dir()
        self.CONFIG_FILE = _paths.config_file_path()
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        initial = loaded if loaded is not None else deepcopy(self.DEFAULTS)
        self._document = ConfigDocument.from_mapping(initial)
        self._persisted_settings: dict[str, Any] = deepcopy(self._settings)
        self._save_defer_depth = 0
        self._save_pending = False
        self._coerce_loaded_settings()

        # Cache mtime for reload() short-circuiting.
        # Many pollers call reload() frequently; avoid re-reading JSON when the
        # file hasn't changed.
        try:
            self._last_reload_mtime_ns: int | None = self.CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            self._last_reload_mtime_ns = None

    @property
    def _settings(self) -> dict[str, Any]:
        """Live flat settings mapping (compat surface for accessors and tests)."""

        return self._document.values

    @_settings.setter
    def _settings(self, value: dict[str, Any]) -> None:
        self._document.replace(value)

    def _load(self, *, retries: int = 3, retry_delay: float = 0.02) -> dict[str, Any] | None:
        """Load settings from file.

        This may race with writers (tray/GUI) updating the JSON file. We retry a few
        times for transient JSONDecodeError (e.g., if a writer truncated then rewrote).
        Returns None if loading fails after retries.
        """

        return _file_storage.load_config_settings(
            config_file=self.CONFIG_FILE,
            defaults=self.DEFAULTS,
            retries=retries,
            retry_delay=retry_delay,
            logger=logger,
        )

    def reload(self) -> None:
        try:
            mtime_ns = self.CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            mtime_ns = None

        # If the config file hasn't changed since our last successful reload,
        # skip disk I/O and JSON parsing.
        if (
            mtime_ns is not None
            and self._last_reload_mtime_ns is not None
            and int(mtime_ns) == int(self._last_reload_mtime_ns)
        ):
            return

        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded
            self._persisted_settings = deepcopy(loaded)
            self._last_reload_mtime_ns = mtime_ns

    def _save(self) -> None:
        """Persist outstanding in-memory changes or raise ``ConfigPersistenceError``.

        While ``batch_update()`` is active, this only marks the transaction dirty.
        Outside a batch, a failed write restores settings from the last successful
        persisted snapshot before raising so ordinary setters cannot leave a
        silently divergent dirty view.
        """

        if self._save_defer_depth > 0:
            self._persist_changes()
            return

        if self._persist_changes():
            return

        self._settings = deepcopy(self._persisted_settings)
        raise ConfigPersistenceError("Could not persist configuration")

    def _persist_changes(self) -> bool:
        if self._save_defer_depth > 0:
            self._save_pending = True
            return True

        updates = {
            key: deepcopy(value)
            for key, value in self._settings.items()
            if key not in self._persisted_settings or self._persisted_settings[key] != value
        }
        removed_keys = set(self._persisted_settings) - set(self._settings)
        if not updates and not removed_keys:
            return True

        merged = _file_storage.merge_config_settings_atomic(
            config_dir=self.CONFIG_DIR,
            config_file=self.CONFIG_FILE,
            defaults=_defaults.DEFAULTS,
            updates=updates,
            removed_keys=removed_keys,
            logger=logger,
        )
        if merged is None:
            return False

        self._settings = merged
        self._persisted_settings = deepcopy(merged)
        try:
            self._last_reload_mtime_ns = self.CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            self._last_reload_mtime_ns = None
        return True

    @contextmanager
    def batch_update(self) -> Iterator[Config]:
        """Persist multiple property updates as one rollback-capable transaction."""

        outermost = self._save_defer_depth == 0
        snapshot = deepcopy(self._settings) if outermost else None
        pending_before = self._save_pending
        self._save_defer_depth += 1
        completed = False
        try:
            yield self
            completed = True
        finally:
            self._save_defer_depth -= 1
            if outermost and not completed and snapshot is not None:
                self._settings = snapshot
                self._save_pending = pending_before
            elif outermost:
                should_save = self._save_pending
                self._save_pending = pending_before
                if should_save and not self._persist_changes():
                    if snapshot is not None:
                        self._settings = snapshot
                    else:
                        self._settings = deepcopy(self._persisted_settings)
                    raise ConfigPersistenceError("Could not persist configuration transaction")

    def apply_perkey_profile_state(
        self,
        colors: Mapping[object, object] | None,
        *,
        effect_brightness: int | None = None,
        perkey_brightness: int | None = None,
        secondary_lighting: Mapping[object, object] | None = None,
    ) -> None:
        """Persist keyboard and optional secondary profile state atomically."""

        if effect_brightness is not None:
            self._settings["brightness"] = self._normalize_brightness_value(effect_brightness)
        if perkey_brightness is not None:
            self._settings["perkey_brightness"] = self._normalize_brightness_value(perkey_brightness)
        self._settings["per_key_colors"] = self._serialize_per_key_colors(dict(colors or {}))
        if secondary_lighting is not None:
            self._merge_secondary_profile_state(secondary_lighting)
        self._save()

    def _merge_secondary_profile_state(self, payload: Mapping[object, object]) -> None:
        raw_areas = payload.get("areas")
        if not isinstance(raw_areas, Mapping):
            return

        # An existing secondary component is an authoritative scene snapshot.
        # Omitted registered routes must therefore become disabled instead of
        # inheriting the previous profile's enabled state.  Unknown/future route
        # entries remain untouched for forward compatibility.
        from keyrgb.core.secondary_device_routes import iter_secondary_routes

        raw_state = self._settings.get("secondary_device_state")
        state: dict[str, object] = raw_state if isinstance(raw_state, dict) else {}
        self._settings["secondary_device_state"] = state

        supplied_keys = {
            str(raw_key or "").strip().lower()
            for raw_key, raw_entry in raw_areas.items()
            if str(raw_key or "").strip() and isinstance(raw_entry, Mapping)
        }
        for route in iter_secondary_routes():
            if not route.supports_profile_state or route.state_key in supplied_keys:
                continue
            existing = state.get(route.state_key)
            disabled: dict[str, object] = dict(existing) if isinstance(existing, dict) else {}
            disabled["enabled"] = False
            state[route.state_key] = disabled

        for raw_key, raw_entry in raw_areas.items():
            key = str(raw_key or "").strip().lower()
            if not key or not isinstance(raw_entry, Mapping):
                continue
            existing = state.get(key)
            merged: dict[str, object] = dict(existing) if isinstance(existing, dict) else {}
            for field, value in raw_entry.items():
                if field == "enabled":
                    if isinstance(value, bool):
                        merged[field] = value
                    elif isinstance(value, (int, float)) and value in (0, 1):
                        merged[field] = bool(value)
                elif field == "color":
                    if (
                        isinstance(value, (list, tuple))
                        and len(value) == 3
                        and all(isinstance(channel, (int, float)) for channel in value)
                    ):
                        merged[field] = [max(0, min(255, int(channel))) for channel in value]
                elif field == "brightness":
                    if isinstance(value, (int, float)):
                        merged[field] = _lighting_coercion.normalize_secondary_brightness_value(value)
                else:
                    merged[str(field)] = value
            state[key] = merged

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:
        return _lighting_coercion.normalize_brightness_value(value)

    @staticmethod
    def _normalize_reactive_brightness_value(value: int) -> int:
        return _lighting_coercion.normalize_precise_brightness_value(value)

    @staticmethod
    def _normalize_reactive_trail_value(value: int) -> int:
        return _lighting_coercion.normalize_trail_percent_value(value)

    def _coerce_loaded_settings(self) -> None:
        """Coerce loaded settings into a consistent, UI-compatible shape."""

        _lighting_coercion.coerce_loaded_settings(
            settings=self._settings,
            config_file=self.CONFIG_FILE,
            save_fn=self._save,
        )

    def settings_view(self) -> ConfigSettingsView:
        """Return a readonly typed snapshot view of current settings."""

        return ConfigSettingsView.from_mapping(self._settings)

    def document(self) -> ConfigDocument:
        """Return the live domain-aware settings document."""

        return self._document

    def domain_view(self, domain: ConfigDomain | str) -> Mapping[str, object]:
        """Readonly projection of one config domain's present keys."""

        resolved = domain if isinstance(domain, ConfigDomain) else ConfigDomain(str(domain))
        return self._document.section(resolved)

    def extras_view(self) -> Mapping[str, object]:
        """Readonly projection of unknown keys retained for forward compatibility."""

        return self._document.extras()

    @overload
    def _get_required_scalar(self, key: Literal["effect"]) -> str: ...

    @overload
    def _get_required_scalar(self, key: Literal["speed"]) -> int: ...

    def _get_required_scalar(self, key: str) -> object:
        return self._settings[key]

    @overload
    def _get_optional_scalar(
        self, key: Literal["return_effect_after_effect"], default: None = None
    ) -> object | None: ...

    @overload
    def _get_optional_scalar(self, key: Literal["effect_speeds"], default: None = None) -> object | None: ...

    def _get_optional_scalar(self, key: str, default: object | None = None) -> object | None:
        return self._settings.get(key, default)

    def _set_scalar(self, key: str, value: object) -> None:
        self._settings[key] = value

    @property
    def effect(self) -> str:
        return self._get_required_scalar("effect")

    @effect.setter
    def effect(self, value: str):
        self._set_scalar("effect", value.lower())
        self._save()

    @property
    def return_effect_after_effect(self) -> str | None:
        value = _normalized_optional_string(self._get_optional_scalar("return_effect_after_effect"))
        if value == "perkey":
            return "perkey"
        return None

    @return_effect_after_effect.setter
    def return_effect_after_effect(self, value: str | None):
        if value is None:
            self._set_scalar("return_effect_after_effect", None)
        else:
            self._set_scalar("return_effect_after_effect", str(value).strip().lower() or None)
        self._save()

    @property
    def speed(self) -> int:
        return self._get_required_scalar("speed")

    @speed.setter
    def speed(self, value: int):
        self._set_scalar("speed", max(0, min(10, value)))
        self._save()

    def _get_effect_speeds(self) -> dict[str, Any] | None:
        return self.effect_speed_snapshot()

    def effect_speed_snapshot(self) -> dict[str, Any] | None:
        """Return detached per-effect speed overrides for read-only consumers."""

        return _effect_speed_boundary.EffectSpeedOverrides.copied_from_settings(
            self._get_optional_scalar("effect_speeds")
        )

    def _effect_speed_overrides(self) -> _effect_speed_boundary.EffectSpeedOverrides | None:
        return _effect_speed_boundary.EffectSpeedOverrides.from_settings(self._get_optional_scalar("effect_speeds"))

    def _ensure_effect_speed_overrides(self) -> _effect_speed_boundary.EffectSpeedOverrides:
        return _effect_speed_boundary.EffectSpeedOverrides.ensure_in_settings(self._settings)

    def _ensure_effect_speeds(self) -> dict[str, Any]:
        return self._ensure_effect_speed_overrides().values

    @staticmethod
    def _normalize_effect_speed(value: object, *, default: int) -> int:
        return max(0, min(10, _lighting_accessors._coerce_int_setting(value, default=default)))

    def get_effect_speed(self, effect_name: str) -> int:
        """Return the saved per-effect speed, falling back to the global speed."""
        global_speed = self.speed
        overrides = self._effect_speed_overrides()
        if overrides is None:
            return global_speed

        has_override, raw_override = overrides.lookup(effect_name)
        if not has_override:
            return global_speed
        return self._normalize_effect_speed(raw_override, default=global_speed)

    def set_effect_speed(self, effect_name: str, speed: int) -> None:
        """Persist a per-effect speed override."""
        if not isinstance(effect_name, str):
            raise TypeError("effect_name must be a str")

        overrides = self._ensure_effect_speed_overrides()
        overrides.assign(effect_name, self._normalize_effect_speed(speed, default=0))
        self._save()
