#!/usr/bin/env python3
"""Lighting-related config accessors shared by Config."""

from __future__ import annotations

import logging
from typing import Any

from src.core.resources.layout_legends import get_layout_legend_pack_ids, load_layout_legend_pack

from ._coercion import normalize_rgb_triplet
from ._lighting_secondary_device_facade import LightingSecondaryDeviceFacade

logger = logging.getLogger("src.core.config.config")
_MISSING = object()
_DEFAULT_SETTING_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_config_exception(message: str, exc: Exception) -> None:
    logger.error(message, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _coerce_int_setting(value: object, *, default: int = 0) -> int:
    if value is None:
        return int(default)
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return int(default)


def _default_setting(defaults: object, key: str, *, fallback_keys: tuple[str, ...] = (), default: object) -> object:
    if isinstance(defaults, dict):
        for candidate_key in (key, *fallback_keys):
            value = defaults.get(candidate_key, _MISSING)
            if value is not _MISSING:
                return value
        return default
    getter = getattr(defaults, "get", None)
    if not callable(getter):
        return default
    try:
        for candidate_key in (key, *fallback_keys):
            value = getter(candidate_key, _MISSING)
            if value is not _MISSING:
                return value
    except _DEFAULT_SETTING_ERRORS as exc:
        _log_config_exception(f"Failed to read config default '{key}': %s", exc)
    return default


def _bool_setting(value: object, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, (bool, int, float, str, list, tuple, dict, set)):
        return bool(value)
    return bool(default)


def _normalize_layout_legend_pack(value: object, *, default: str = "auto") -> str:
    normalized = str(value or default).strip().lower()
    if not normalized or normalized == "auto":
        return "auto"

    available = set(get_layout_legend_pack_ids())
    if normalized in available and load_layout_legend_pack(normalized):
        return normalized
    return str(default or "auto").strip().lower() or "auto"


class LightingConfigAccessors(LightingSecondaryDeviceFacade):
    """Color and brightness accessors for the Config model."""

    _settings: dict[str, Any]
    DEFAULTS: object

    # Provided by the implementing class (Config).
    def _save(self) -> None:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _normalize_reactive_brightness_value(value: int) -> int:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _normalize_reactive_trail_value(value: int) -> int:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:  # type: ignore[empty-body]
        ...

    def _setting(self, key: str, default: object) -> object:
        return self._settings.get(key, default)

    def _default_setting_value(
        self,
        key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object,
    ) -> object:
        return _default_setting(self.DEFAULTS, key, fallback_keys=fallback_keys, default=default)

    def _setting_or_default_on_none(
        self,
        key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object,
    ) -> object:
        value = self._setting(key, None)
        if value is None:
            return self._default_setting_value(key, fallback_keys=fallback_keys, default=default)
        return value

    def _default_setting_adapter(
        self,
        defaults: object,
        key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object,
    ) -> object:
        return _default_setting(defaults, key, fallback_keys=fallback_keys, default=default)

    def _brightness_default_int(self) -> int:
        return _coerce_int_setting(self._setting("brightness", 0), default=0)

    def _perkey_brightness_raw(self) -> object:
        return self._settings.get("perkey_brightness", self._settings.get("brightness", 0))

    @property
    def brightness(self) -> int:
        if self._settings.get("effect", "none") == "perkey":
            return _coerce_int_setting(self._perkey_brightness_raw(), default=0)
        return _coerce_int_setting(self._settings.get("brightness", 0), default=0)

    @brightness.setter
    def brightness(self, value: int):
        if self._settings.get("effect", "none") == "perkey":
            self._settings["perkey_brightness"] = self._normalize_brightness_value(value)
        else:
            self._settings["brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def effect_brightness(self) -> int:
        return int(self._settings.get("brightness", 0) or 0)

    @effect_brightness.setter
    def effect_brightness(self, value: int):
        self._settings["brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def perkey_brightness(self) -> int:
        return int(self._perkey_brightness_raw() or 0)  # type: ignore[call-overload]

    @perkey_brightness.setter
    def perkey_brightness(self, value: int):
        self._settings["perkey_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def reactive_brightness(self) -> int:
        return _coerce_int_setting(
            self._setting("reactive_brightness", self._setting("brightness", 0)),
            default=self._brightness_default_int(),
        )

    @reactive_brightness.setter
    def reactive_brightness(self, value: int):
        self._settings["reactive_brightness"] = self._normalize_reactive_brightness_value(value)
        self._save()

    @property
    def reactive_trail_percent(self) -> int:
        return _coerce_int_setting(self._settings.get("reactive_trail_percent", 50), default=50)

    @reactive_trail_percent.setter
    def reactive_trail_percent(self, value: int):
        self._settings["reactive_trail_percent"] = self._normalize_reactive_trail_value(value)
        self._save()

    @property
    def color(self) -> tuple:
        return tuple(self._settings["color"])

    @color.setter
    def color(self, value: tuple):
        self._settings["color"] = list(value)
        self._save()

    @property
    def direction(self) -> str | None:
        value = self._settings.get("direction", None)
        if value is None:
            return None
        return str(value).strip().lower() or None

    @direction.setter
    def direction(self, value: str | None):
        self._settings["direction"] = value
        self._save()

    @property
    def tray_device_context(self) -> str:
        raw = self._settings.get("tray_device_context", "keyboard")
        if raw is None or not isinstance(raw, str):
            return "keyboard"
        value = raw.strip().lower()
        return value or "keyboard"

    @tray_device_context.setter
    def tray_device_context(self, value: str | None) -> None:
        if value is None:
            normalized = "keyboard"
        elif isinstance(value, str):
            normalized = value.strip().lower()
        else:
            normalized = "keyboard"
        self._settings["tray_device_context"] = normalized or "keyboard"
        self._save()

    @property
    def reactive_color(self) -> tuple[int, int, int]:
        raw = self._setting_or_default_on_none("reactive_color", default=[255, 255, 255])
        return normalize_rgb_triplet(raw)

    @reactive_color.setter
    def reactive_color(self, value: tuple[int, int, int] | tuple) -> None:
        self._settings["reactive_color"] = list(normalize_rgb_triplet(value))
        self._save()

    @property
    def reactive_use_manual_color(self) -> bool:
        return _bool_setting(self._settings.get("reactive_use_manual_color", False), default=False)

    @reactive_use_manual_color.setter
    def reactive_use_manual_color(self, value: bool):
        self._settings["reactive_use_manual_color"] = bool(value)
        self._save()

    @property
    def layout_legend_pack(self) -> str:
        return _normalize_layout_legend_pack(self._settings.get("layout_legend_pack", "auto"), default="auto")

    @layout_legend_pack.setter
    def layout_legend_pack(self, value: str) -> None:
        self._settings["layout_legend_pack"] = _normalize_layout_legend_pack(value, default="auto")
        self._save()

    @property
    def per_key_colors(self) -> dict:
        return self._deserialize_per_key_colors(self._settings.get("per_key_colors", {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings["per_key_colors"] = self._serialize_per_key_colors(value or {})
        self._save()
