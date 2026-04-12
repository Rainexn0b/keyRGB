from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from threading import RLock
from typing import Protocol, cast

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD
from src.core.effects.software_targets import normalize_software_effect_target
from src.tray.secondary_device_routes import SecondaryDeviceRoute, route_for_context_entry
from src.core.utils.exceptions import is_permission_denied
from src.tray.ui.menu_status import device_context_controls_available, device_context_entries


logger = logging.getLogger(__name__)

_ENGINE_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)
_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
_SECONDARY_TARGET_RUNTIME_EXCEPTIONS = (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError)
_TRAY_CALLBACK_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


class _LightbarDeviceProtocol(Protocol):
    def set_color(self, color: object, *, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


class _SecondarySoftwareTargetProtocol(Protocol):
    key: str

    def set_color(self, color: object, *, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


class _SoftwareTargetTrayProtocol(Protocol):
    @property
    def config(self) -> object: ...

    @property
    def engine(self) -> object: ...

    @property
    def is_off(self) -> bool: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


class _PermissionIssueTrayProtocol(Protocol):
    def _notify_permission_issue(self, exc: Exception) -> None: ...


class _CachedSecondarySoftwareTarget:
    supports_per_key = False

    def __init__(self, *, key: str, route: SecondaryDeviceRoute) -> None:
        self.key = str(key or "lightbar")
        self.device_type = str(route.device_type)
        self._route = route
        self._lock = RLock()
        self._device: _LightbarDeviceProtocol | None = None

    @property
    def device(self) -> "_CachedSecondarySoftwareTarget":
        return self

    def set_color(self, color: object, *, brightness: int) -> None:
        def _apply(device: _LightbarDeviceProtocol) -> None:
            device.set_color(color, brightness=int(brightness))

        self._with_device(_apply)

    def turn_off(self) -> None:
        self._with_device(lambda device: device.turn_off())

    def _with_device(self, operation: Callable[[_LightbarDeviceProtocol], None]) -> None:
        with self._lock:
            device = self._device
            if device is None:
                device = self._route.get_device()
                self._device = device
            try:
                operation(device)
            # @quality-exception exception-transparency: any device-operation failure should invalidate the cached handle before re-raising
            except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS:
                self._device = None
                raise


def _try_log_event(tray: _SoftwareTargetTrayProtocol, source: str, action: str, **fields: object) -> None:
    try:
        tray._log_event(source, action, **fields)
    except _TRAY_CALLBACK_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: tray event logging is a best-effort runtime boundary and must never block tray actions
        logger.exception("Tray event logging failed: %s", exc)


def _notify_permission_issue_or_none(tray: _SoftwareTargetTrayProtocol) -> Callable[[Exception], None] | None:
    try:
        notify_permission_issue = cast(_PermissionIssueTrayProtocol, tray)._notify_permission_issue
    except AttributeError:
        return None
    if not callable(notify_permission_issue):
        return None
    return notify_permission_issue


def configure_engine_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    target = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    _set_engine_attr_best_effort(
        tray,
        "software_effect_target",
        target,
        error_msg="Failed to sync engine software target: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "secondary_software_targets_provider",
        lambda tray_ref=tray: secondary_software_render_targets(tray_ref),
        error_msg="Failed to install secondary software target provider: %s",
    )


def apply_software_effect_target_selection(tray: _SoftwareTargetTrayProtocol, target: str) -> str:
    normalized = normalize_software_effect_target(target)
    previous = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))

    _set_config_attr_best_effort(
        tray,
        "software_effect_target",
        normalized,
        error_msg="Failed to persist software effect target selection: %s",
    )

    configure_engine_software_targets(tray)
    _try_log_event(tray, "menu", "set_software_effect_target", old=previous, new=normalized)

    if normalized != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE and not bool(getattr(tray, "is_off", False)):
        restore_secondary_software_targets(tray)

    return normalized


def software_effect_target_has_auxiliary_devices(tray: object) -> bool:
    return bool(_secondary_target_entries(tray))


def software_effect_target_routes_aux_devices(tray: _SoftwareTargetTrayProtocol) -> bool:
    if not software_effect_target_has_auxiliary_devices(tray):
        return False
    current = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    return current == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE


def secondary_software_render_targets(tray: _SoftwareTargetTrayProtocol) -> list[_SecondarySoftwareTargetProtocol]:
    cache = _proxy_cache(tray)
    targets: list[_SecondarySoftwareTargetProtocol] = []
    for entry in _secondary_target_entries(tray):
        route = route_for_context_entry(entry)
        if route is None or not bool(route.supports_uniform_color) or not bool(route.supports_software_target):
            continue
        key = str(entry.get("key") or route.device_type)
        target = cache.get(key)
        if target is None:
            target = _CachedSecondarySoftwareTarget(key=key, route=route)
            cache[key] = target
        targets.append(target)
    return targets


def restore_secondary_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    for entry, target in _iter_secondary_targets(tray):
        try:
            _restore_target_from_config(tray, entry=entry, target=target)
        except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
            _handle_secondary_target_error(tray, exc, action="restore_secondary_software_target")


def turn_off_secondary_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    for _entry, target in _iter_secondary_targets(tray):
        try:
            target.turn_off()
        except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
            _handle_secondary_target_error(tray, exc, action="turn_off_secondary_software_target")


def software_effect_target_options(tray: object) -> list[dict[str, object]]:
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


def _secondary_target_entries(tray: object) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for entry in device_context_entries(tray):
        if str(entry.get("device_type") or "keyboard").strip().lower() == "keyboard":
            continue
        if not device_context_controls_available(tray, entry):
            continue
        entries.append(entry)
    return entries


def _proxy_cache(tray: _SoftwareTargetTrayProtocol) -> dict[str, _SecondarySoftwareTargetProtocol]:
    existing = getattr(tray, "software_target_proxy_cache", None)
    if isinstance(existing, dict):
        return existing
    cache: dict[str, _SecondarySoftwareTargetProtocol] = {}
    try:
        setattr(tray, "software_target_proxy_cache", cache)
    except (AttributeError, TypeError):
        pass
    except RuntimeError as exc:
        _log_boundary_exception(tray, "Failed to store software target proxy cache: %s", exc)
    return cache


def _iter_secondary_targets(
    tray: _SoftwareTargetTrayProtocol,
) -> Iterator[tuple[dict[str, str], _SecondarySoftwareTargetProtocol]]:
    targets_by_key = {target.key: target for target in secondary_software_render_targets(tray)}
    for entry in _secondary_target_entries(tray):
        key = str(entry.get("key") or "")
        target = targets_by_key.get(key)
        if target is None:
            continue
        yield entry, target


def _restore_target_from_config(
    tray: _SoftwareTargetTrayProtocol,
    *,
    entry: dict[str, str],
    target: _SecondarySoftwareTargetProtocol,
) -> None:
    route = route_for_context_entry(entry)
    if route is None:
        return

    config = getattr(tray, "config", None)
    if config is None:
        return

    brightness_getter = getattr(config, "get_secondary_device_brightness", None)
    color_getter = getattr(config, "get_secondary_device_color", None)
    if callable(brightness_getter):
        brightness = int(
            brightness_getter(
                str(route.state_key), fallback_keys=tuple(filter(None, (route.config_brightness_attr,))), default=0
            )
            or 0
        )
    else:
        brightness_attr = str(route.config_brightness_attr or "").strip()
        if not brightness_attr:
            return
        brightness = int(getattr(config, brightness_attr, 0) or 0)
    if brightness <= 0:
        target.turn_off()
        return

    if callable(color_getter):
        raw_color = color_getter(
            str(route.state_key), fallback_keys=tuple(filter(None, (route.config_color_attr,))), default=(255, 0, 0)
        )
    else:
        color_attr = str(route.config_color_attr or "").strip()
        if not color_attr:
            return
        raw_color = getattr(config, color_attr, (255, 0, 0))
    color = tuple(raw_color or (255, 0, 0))
    target.set_color(color, brightness=brightness)


def _handle_secondary_target_error(tray: _SoftwareTargetTrayProtocol, exc: Exception, *, action: str) -> None:
    if is_permission_denied(exc):
        notify_permission_issue = _notify_permission_issue_or_none(tray)
        if notify_permission_issue is None:
            _log_boundary_exception(tray, f"Error during {action}: %s", exc)
            return
        try:
            notify_permission_issue(exc)
            return
        except _TRAY_CALLBACK_RUNTIME_EXCEPTIONS as notify_exc:  # @quality-exception exception-transparency: notification callback is a best-effort UI boundary; fall through to traceback logging
            _log_boundary_exception(
                tray, "Failed to notify permission issue for secondary software target: %s", notify_exc
            )

    _log_boundary_exception(tray, f"Error during {action}: %s", exc)


def _set_engine_attr_best_effort(
    tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str
) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    try:
        setattr(engine, attr, value)
    except AttributeError:
        return
    except _ENGINE_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _set_config_attr_best_effort(
    tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str
) -> None:
    config = getattr(tray, "config", None)
    if config is None:
        return

    try:
        setattr(config, attr, value)
    except AttributeError:
        return
    except _CONFIG_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _log_boundary_exception(tray: _SoftwareTargetTrayProtocol, msg: str, exc: Exception) -> None:
    try:
        tray._log_exception(msg, exc)
        return
    except _TRAY_CALLBACK_RUNTIME_EXCEPTIONS as log_exc:  # @quality-exception exception-transparency: tray logger callback may raise arbitrary runtime errors; fallback to module logging
        logger.exception("Tray exception logger failed while logging boundary: %s", log_exc)

    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


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
