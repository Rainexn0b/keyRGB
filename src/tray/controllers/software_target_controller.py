from __future__ import annotations

from threading import RLock
from typing import Any

from src.core.backends.ite8233.backend import Ite8233Backend
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.exceptions import is_permission_denied
from src.tray.ui.menu_status import device_context_controls_available, device_context_entries

from ._lighting_controller_helpers import try_log_event


class _CachedLightbarSoftwareTarget:
    supports_per_key = False
    device_type = "lightbar"

    def __init__(self, *, key: str) -> None:
        self.key = str(key or "lightbar")
        self._lock = RLock()
        self._device: Any | None = None

    @property
    def device(self) -> "_CachedLightbarSoftwareTarget":
        return self

    def set_color(self, color, *, brightness: int) -> None:
        def _apply(device: Any) -> None:
            device.set_color(color, brightness=int(brightness))

        self._with_device(_apply)

    def turn_off(self) -> None:
        self._with_device(lambda device: device.turn_off())

    def _with_device(self, operation) -> None:
        with self._lock:
            device = self._device
            if device is None:
                device = Ite8233Backend().get_device()
                self._device = device
            try:
                operation(device)
            except Exception:
                self._device = None
                raise


def configure_engine_software_targets(tray: Any) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    target = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    try:
        engine.software_effect_target = target
    except Exception:
        pass

    try:
        engine.secondary_software_targets_provider = lambda tray_ref=tray: secondary_software_render_targets(tray_ref)
    except Exception:
        pass


def apply_software_effect_target_selection(tray: Any, target: str) -> str:
    normalized = normalize_software_effect_target(target)
    previous = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))

    try:
        tray.config.software_effect_target = normalized
    except Exception:
        pass

    configure_engine_software_targets(tray)
    try_log_event(tray, "menu", "set_software_effect_target", old=previous, new=normalized)

    if normalized != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE and not bool(getattr(tray, "is_off", False)):
        restore_secondary_software_targets(tray)

    return normalized


def software_effect_target_has_auxiliary_devices(tray: Any) -> bool:
    return bool(_secondary_target_entries(tray))


def software_effect_target_routes_aux_devices(tray: Any) -> bool:
    if not software_effect_target_has_auxiliary_devices(tray):
        return False
    current = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    return current == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE


def secondary_software_render_targets(tray: Any) -> list[object]:
    cache = _proxy_cache(tray)
    targets: list[object] = []
    for entry in _secondary_target_entries(tray):
        device_type = str(entry.get("device_type") or "").strip().lower()
        if device_type != "lightbar":
            continue
        key = str(entry.get("key") or device_type)
        target = cache.get(key)
        if target is None:
            target = _CachedLightbarSoftwareTarget(key=key)
            cache[key] = target
        targets.append(target)
    return targets


def restore_secondary_software_targets(tray: Any) -> None:
    for entry, target in _iter_secondary_targets(tray):
        try:
            _restore_target_from_config(tray, entry=entry, target=target)
        except Exception as exc:
            _handle_secondary_target_error(tray, exc, action="restore_secondary_software_target")


def turn_off_secondary_software_targets(tray: Any) -> None:
    for _entry, target in _iter_secondary_targets(tray):
        try:
            target.turn_off()
        except Exception as exc:
            _handle_secondary_target_error(tray, exc, action="turn_off_secondary_software_target")


def software_effect_target_options(tray: Any) -> list[dict[str, object]]:
    aux_available = software_effect_target_has_auxiliary_devices(tray)
    return [
        {
            "key": SOFTWARE_EFFECT_TARGET_KEYBOARD,
            "label": "Keyboard Only",
            "enabled": True,
        },
        {
            "key": SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
            "label": "All Compatible Devices",
            "enabled": aux_available,
        },
    ]


def _secondary_target_entries(tray: Any) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for entry in device_context_entries(tray):
        if str(entry.get("device_type") or "keyboard").strip().lower() == "keyboard":
            continue
        if not device_context_controls_available(tray, entry):
            continue
        entries.append(entry)
    return entries


def _proxy_cache(tray: Any) -> dict[str, object]:
    existing = getattr(tray, "_software_target_proxy_cache", None)
    if isinstance(existing, dict):
        return existing
    cache: dict[str, object] = {}
    try:
        tray._software_target_proxy_cache = cache
    except Exception:
        pass
    return cache


def _iter_secondary_targets(tray: Any):
    targets_by_key = {
        str(getattr(target, "key", "")): target
        for target in secondary_software_render_targets(tray)
    }
    for entry in _secondary_target_entries(tray):
        key = str(entry.get("key") or "")
        target = targets_by_key.get(key)
        if target is None:
            continue
        yield entry, target


def _restore_target_from_config(tray: Any, *, entry: dict[str, str], target: Any) -> None:
    device_type = str(entry.get("device_type") or "").strip().lower()
    if device_type != "lightbar":
        return

    brightness = int(getattr(tray.config, "lightbar_brightness", 0) or 0)
    if brightness <= 0:
        target.turn_off()
        return

    color = tuple(getattr(tray.config, "lightbar_color", (255, 0, 0)) or (255, 0, 0))
    target.set_color(color, brightness=brightness)


def _handle_secondary_target_error(tray: Any, exc: Exception, *, action: str) -> None:
    notify = getattr(tray, "_notify_permission_issue", None)
    if is_permission_denied(exc) and callable(notify):
        try:
            notify(exc)
            return
        except Exception:
            pass

    log_exception = getattr(tray, "_log_exception", None)
    if callable(log_exception):
        try:
            log_exception(f"Error during {action}: %s", exc)
            return
        except Exception:
            pass


__all__ = [
    "apply_software_effect_target_selection",
    "configure_engine_software_targets",
    "restore_secondary_software_targets",
    "secondary_software_render_targets",
    "software_effect_target_has_auxiliary_devices",
    "software_effect_target_options",
    "software_effect_target_routes_aux_devices",
    "turn_off_secondary_software_targets",
]