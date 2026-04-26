#!/usr/bin/env python3
"""Secondary-device lighting facade shared by Config lighting accessors."""

from __future__ import annotations

from typing import Any

from . import _secondary_device_accessors as secondary_device_accessors


def _coerce_int_setting(value: object, *, default: int = 0) -> int:
    if value is None:
        return int(default)
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return int(default)


class LightingSecondaryDeviceFacade:
    """Secondary-device, lightbar, and auxiliary route accessors for Config."""

    _settings: dict[str, Any]
    DEFAULTS: object

    # Provided by the implementing class (Config).
    def _save(self) -> None:  # type: ignore[empty-body]
        ...

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:  # type: ignore[empty-body]
        ...

    def _default_setting_adapter(
        self,
        defaults: object,
        key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object,
    ) -> object: ...

    def _secondary_device_state(self) -> dict[str, Any]:
        return secondary_device_accessors.secondary_device_state(self)

    def _normalize_secondary_state_key(self, value: object, *, default: str = "device") -> str:
        return secondary_device_accessors.normalize_secondary_state_key(value, default=default)

    def get_secondary_device_brightness(
        self,
        state_key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: int = 25,
    ) -> int:
        return secondary_device_accessors.get_secondary_device_brightness(
            self,
            state_key,
            fallback_keys=fallback_keys,
            default=default,
            default_setting_fn=self._default_setting_adapter,
            coerce_int_setting_fn=_coerce_int_setting,
        )

    def set_secondary_device_brightness(
        self,
        state_key: str,
        value: int,
        *,
        compatibility_key: str | None = None,
    ) -> None:
        secondary_device_accessors.set_secondary_device_brightness(
            self,
            state_key,
            value,
            compatibility_key=compatibility_key,
        )

    def get_secondary_device_color(
        self,
        state_key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: tuple[int, int, int] = (255, 0, 0),
    ) -> tuple[int, int, int]:
        return secondary_device_accessors.get_secondary_device_color(
            self,
            state_key,
            fallback_keys=fallback_keys,
            default=default,
            default_setting_fn=self._default_setting_adapter,
        )

    def set_secondary_device_color(
        self,
        state_key: str,
        value: tuple[int, int, int] | tuple,
        *,
        compatibility_key: str | None = None,
        default: tuple[int, int, int] = (255, 0, 0),
    ) -> None:
        secondary_device_accessors.set_secondary_device_color(
            self,
            state_key,
            value,
            compatibility_key=compatibility_key,
            default=default,
        )

    @property
    def lightbar_brightness(self) -> int:
        return secondary_device_accessors.get_lightbar_brightness(
            self,
            default_setting_fn=self._default_setting_adapter,
            coerce_int_setting_fn=_coerce_int_setting,
        )

    @lightbar_brightness.setter
    def lightbar_brightness(self, value: int) -> None:
        secondary_device_accessors.set_lightbar_brightness(self, value)

    @property
    def lightbar_color(self) -> tuple[int, int, int]:
        return secondary_device_accessors.get_lightbar_color(
            self,
            default_setting_fn=self._default_setting_adapter,
        )

    @lightbar_color.setter
    def lightbar_color(self, value: tuple[int, int, int] | tuple) -> None:
        secondary_device_accessors.set_lightbar_color(self, value)
