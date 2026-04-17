from __future__ import annotations

from collections.abc import Callable, Iterator
from threading import RLock
from typing import Protocol, TypeVar, cast

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD
from src.core.effects.software_targets import normalize_software_effect_target
from src.tray.secondary_device_routes import SecondaryDeviceRoute, route_for_context_entry
from src.tray.ui.menu_status import DeviceContextEntry


_TrayT = TypeVar("_TrayT")
_SECONDARY_TARGET_RUNTIME_EXCEPTIONS = (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError)


class _LightbarDeviceProtocol(Protocol):
    def set_color(self, color: object, *, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


class _SecondarySoftwareTargetProtocol(Protocol):
    key: str

    def set_color(self, color: object, *, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


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

    def _invalidate_cached_device(self) -> None:
        self._device = None

    def _with_device(self, operation: Callable[[_LightbarDeviceProtocol], None]) -> None:
        with self._lock:
            device = self._device
            if device is None:
                device = self._route.get_device()
                self._device = device
            try:
                operation(device)
            except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS:
                self._invalidate_cached_device()
                raise


def _secondary_target_entries(
    tray: object,
    *,
    device_context_entries_fn: Callable[[object], list[DeviceContextEntry]],
    device_context_controls_available_fn: Callable[[object, DeviceContextEntry], bool],
) -> list[DeviceContextEntry]:
    entries: list[DeviceContextEntry] = []
    for entry in device_context_entries_fn(tray):
        if str(entry.get("device_type") or "keyboard").strip().lower() == "keyboard":
            continue
        if not device_context_controls_available_fn(tray, entry):
            continue
        entries.append(entry)
    return entries


def _proxy_cache(
    tray: _TrayT,
    *,
    on_store_cache_failure: Callable[[Exception], None] | None = None,
) -> dict[str, _SecondarySoftwareTargetProtocol]:
    existing = getattr(tray, "software_target_proxy_cache", None)
    if isinstance(existing, dict):
        return cast(dict[str, _SecondarySoftwareTargetProtocol], existing)

    cache: dict[str, _SecondarySoftwareTargetProtocol] = {}
    try:
        setattr(tray, "software_target_proxy_cache", cache)
    except (AttributeError, TypeError):
        pass
    except RuntimeError as exc:
        if on_store_cache_failure is not None:
            on_store_cache_failure(exc)
    return cache


def _iter_secondary_targets(
    tray: _TrayT,
    *,
    secondary_target_entries_fn: Callable[[_TrayT], list[DeviceContextEntry]],
    secondary_software_render_targets_fn: Callable[[_TrayT], list[_SecondarySoftwareTargetProtocol]],
) -> Iterator[tuple[DeviceContextEntry, _SecondarySoftwareTargetProtocol]]:
    targets_by_key = {target.key: target for target in secondary_software_render_targets_fn(tray)}
    for entry in secondary_target_entries_fn(tray):
        key = str(entry.get("key") or "")
        target = targets_by_key.get(key)
        if target is None:
            continue
        yield entry, target


def secondary_software_render_targets(
    tray: _TrayT,
    *,
    secondary_target_entries_fn: Callable[[_TrayT], list[DeviceContextEntry]],
    proxy_cache_fn: Callable[[_TrayT], dict[str, _SecondarySoftwareTargetProtocol]],
    cached_secondary_target_cls: type[_CachedSecondarySoftwareTarget],
) -> list[_SecondarySoftwareTargetProtocol]:
    cache = proxy_cache_fn(tray)
    targets: list[_SecondarySoftwareTargetProtocol] = []
    for entry in secondary_target_entries_fn(tray):
        route = route_for_context_entry(entry)
        if route is None or not bool(route.supports_uniform_color) or not bool(route.supports_software_target):
            continue
        key = str(entry.get("key") or route.device_type)
        target = cache.get(key)
        if target is None:
            target = cached_secondary_target_cls(key=key, route=route)
            cache[key] = target
        targets.append(target)
    return targets


def software_effect_target_has_auxiliary_devices(
    tray: _TrayT,
    *,
    secondary_target_entries_fn: Callable[[_TrayT], list[DeviceContextEntry]],
) -> bool:
    return bool(secondary_target_entries_fn(tray))


def software_effect_target_options(
    tray: _TrayT,
    *,
    has_auxiliary_devices_fn: Callable[[_TrayT], bool],
) -> list[dict[str, object]]:
    aux_available = has_auxiliary_devices_fn(tray)
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


def software_effect_target_routes_aux_devices(
    tray: _TrayT,
    *,
    has_auxiliary_devices_fn: Callable[[_TrayT], bool],
) -> bool:
    if not has_auxiliary_devices_fn(tray):
        return False

    current = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    return current == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
