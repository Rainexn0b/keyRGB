from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, SupportsInt, runtime_checkable

from src.tray.secondary_device_routes import SecondaryDeviceRoute


class SafeIntAttrReader(Protocol):
    def __call__(
        self,
        obj: object,
        attr_name: str,
        *,
        default: int = 0,
        min_v: int | None = None,
        max_v: int | None = None,
    ) -> int: ...


@runtime_checkable
class SecondaryBrightnessConfig(Protocol):
    def get_secondary_device_brightness(
        self,
        state_key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: int = 0,
    ) -> SupportsInt | str | None: ...


def state_key(route: SecondaryDeviceRoute) -> str:
    return str(getattr(route, "state_key", getattr(route, "device_type", "device")) or "device")


def current_brightness(
    config: object | None,
    route: SecondaryDeviceRoute | None,
    *,
    safe_int_attr: SafeIntAttrReader | None = None,
) -> int:
    if config is None or route is None:
        return 0

    fallback_keys = (str(route.config_brightness_attr),) if route.config_brightness_attr else ()
    if isinstance(config, SecondaryBrightnessConfig):
        current = config.get_secondary_device_brightness(
            state_key(route),
            fallback_keys=fallback_keys,
            default=0,
        )
        return int(current or 0)

    attr_name = str(route.config_brightness_attr or "").strip()
    if not attr_name:
        return 0
    if safe_int_attr is not None:
        return safe_int_attr(config, attr_name, default=0)
    raw_brightness = getattr(config, attr_name, 0)
    if raw_brightness is None:
        return 0
    return int(raw_brightness)


def is_off(
    config: object | None,
    route: SecondaryDeviceRoute | None,
    *,
    safe_int_attr: SafeIntAttrReader | None = None,
) -> bool:
    return current_brightness(config, route, safe_int_attr=safe_int_attr) <= 0


def restore_hints(tray: object) -> dict[str, int]:
    hints = getattr(tray, "secondary_restore_brightness", None)
    if isinstance(hints, dict):
        return hints
    hints = {}
    setattr(tray, "secondary_restore_brightness", hints)
    return hints


def cache_restore_brightness(tray: object, route: SecondaryDeviceRoute, brightness: int) -> None:
    if int(brightness) <= 0:
        return
    restore_hints(tray)[state_key(route)] = int(brightness)


def restore_brightness(
    tray: object,
    route: SecondaryDeviceRoute,
    *,
    current_brightness_fn: Callable[[], int],
    default: int = 25,
) -> int:
    hint = restore_hints(tray).get(state_key(route))
    if hint is not None and int(hint) > 0:
        return int(hint)

    current = int(current_brightness_fn())
    if current > 0:
        return current
    return int(default)


__all__ = [
    "SafeIntAttrReader",
    "SecondaryBrightnessConfig",
    "cache_restore_brightness",
    "current_brightness",
    "is_off",
    "restore_brightness",
    "restore_hints",
    "state_key",
]
