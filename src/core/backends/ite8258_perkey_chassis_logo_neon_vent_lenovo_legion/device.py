from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import SupportsIndex, SupportsInt, cast

from . import protocol

_logger = logging.getLogger(__name__)
FeatureReportWriter = Callable[[bytes], int | None]
IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def _coerce_rgb(color) -> tuple[int, int, int]:
    try:
        red, green, blue = color
    except (TypeError, ValueError) as exc:
        raise ValueError("color must be an RGB 3-tuple") from exc
    return (
        protocol.clamp_channel(red),
        protocol.clamp_channel(green),
        protocol.clamp_channel(blue),
    )


def _coerce_led_id(key_id: object) -> int:
    if isinstance(key_id, tuple):
        if len(key_id) != 2:
            raise ValueError("tuple key ids must be (row, col)")
        row, col = key_id
        return protocol.led_id_from_row_col(int(row), int(col))
    return _coerce_int(key_id) & 0xFFFF


def _coerce_led_id_or_none(key_id: object) -> int | None:
    if isinstance(key_id, tuple):
        if len(key_id) != 2:
            raise ValueError("tuple key ids must be (row, col)")
        row, col = key_id
        try:
            return protocol.led_id_from_row_col(int(row), int(col))
        except ValueError:
            return None
    return _coerce_led_id(key_id)


def _normalize_effect_name(effect_data: object) -> str:
    if isinstance(effect_data, dict):
        effect_value = effect_data.get("name", effect_data.get("effect", ""))
    elif isinstance(effect_data, (list, tuple)) and effect_data:
        effect_value = effect_data[0]
    else:
        effect_value = effect_data
    return str(effect_value or "").strip().lower().replace(" ", "_")


class Ite8258ChassisKeyboardDevice:
    """Keyboard-first Lenovo Gen10 ITE 8258 runtime wrapper."""

    keyrgb_hw_speed_policy = "direct"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        *,
        profile_id: int = protocol.DEFAULT_PROFILE_ID,
        current_brightness: int = protocol.UI_BRIGHTNESS_MAX,
        transport: object | None = None,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._transport = transport
        self._profile_id = int(profile_id) & 0xFF
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)
        self._is_off = self._current_brightness <= 0

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8258 chassis feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._send(report)

    def _prepare_profile_write(self) -> None:
        self._send(protocol.build_switch_profile_report(self._profile_id))
        self._send(protocol.build_set_direct_mode_report(enabled=False, profile_id=self._profile_id))

    def _apply_groups(self, groups: Sequence[protocol.Ite8258ChassisGroup], *, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._prepare_profile_write()
        self._write_reports(protocol.build_save_profile_reports(self._profile_id, groups))
        self._send(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_brightness = level
        self._is_off = False

    def turn_off(self) -> None:
        self._prepare_profile_write()
        self._send(protocol.build_turn_off_report(profile_id=self._profile_id))
        self._current_brightness = 0
        self._is_off = True

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._send(protocol.build_switch_profile_report(self._profile_id))
        self._send(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_brightness = level
        self._is_off = False

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        if rgb == (0, 0, 0) or int(brightness) <= 0:
            self.turn_off()
            return
        self._apply_groups(protocol.build_uniform_static_groups(rgb), brightness=brightness)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del enable_user_mode
        if not isinstance(color_map, Mapping) or not color_map:
            self.turn_off()
            return

        led_colors: dict[int, tuple[int, int, int]] = {}
        for key_id, color in color_map.items():
            led_id = _coerce_led_id_or_none(key_id)
            if led_id is None:
                continue
            led_colors[led_id] = _coerce_rgb(color)

        key_colors = protocol.build_static_led_map(led_colors)
        if all(color == (0, 0, 0) for color in key_colors):
            self.turn_off()
            return

        self._apply_groups(protocol.build_static_groups(key_colors), brightness=brightness)

    def set_effect(self, effect_data) -> None:
        effect_name = _normalize_effect_name(effect_data)
        brightness = self._current_brightness
        speed_raw = protocol.raw_speed_from_ui(protocol.UI_SPEED_MAX // 2)
        direction = None
        color = None

        if isinstance(effect_data, Mapping):
            if "brightness" in effect_data:
                brightness = protocol.clamp_ui_brightness(effect_data.get("brightness", brightness))
            if "speed" in effect_data:
                speed_raw = protocol.raw_speed_from_ui(effect_data.get("speed", protocol.UI_SPEED_MAX // 2))
            direction = effect_data.get("direction", None)
            color = effect_data.get("color", None)

        groups = protocol.build_effect_groups(effect_name, speed=speed_raw, color=color, direction=direction)
        self._apply_groups(groups, brightness=brightness)

    def close(self) -> None:
        transport = self._transport
        if transport is not None:
            self._transport = None
            close_fn = getattr(transport, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except (OSError, RuntimeError, ValueError):
                    _logger.debug("Error closing ITE 8258 chassis HID transport", exc_info=True)


class Ite8258ChassisZoneDevice:
    """Uniform-color zone device for a single surface of the Gen10 composite controller.

    Surfaces include the lid logo, the front neon strip, and the side/rear vent
    LED groups. Each zone device shares the parent keyboard's hidraw transport
    and operates on a fixed set of 16-bit LED IDs.
    """

    keyrgb_hw_speed_policy = "direct"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        *,
        zone_name: str,
        led_ids: tuple[int, ...],
        profile_id: int = protocol.DEFAULT_PROFILE_ID,
        current_brightness: int = protocol.UI_BRIGHTNESS_MAX,
        transport: object | None = None,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._transport = transport
        self._zone_name = str(zone_name)
        self._led_ids = tuple(int(led_id) & 0xFFFF for led_id in led_ids)
        self._profile_id = int(profile_id) & 0xFF
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)
        self._is_off = self._current_brightness <= 0

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError(f"Could not send ITE 8258 chassis {self._zone_name} feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._send(report)

    def _prepare_profile_write(self) -> None:
        self._send(protocol.build_switch_profile_report(self._profile_id))
        self._send(protocol.build_set_direct_mode_report(enabled=False, profile_id=self._profile_id))

    def _apply_groups(self, groups: Sequence[protocol.Ite8258ChassisGroup], *, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._prepare_profile_write()
        self._write_reports(protocol.build_save_profile_reports(self._profile_id, groups))
        self._send(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_brightness = level
        self._is_off = False

    def turn_off(self) -> None:
        if not self._led_ids:
            self._is_off = True
            return

        self._prepare_profile_write()
        self._write_reports(
            protocol.build_save_profile_reports(
                self._profile_id,
                protocol.build_uniform_static_groups_for_leds(self._led_ids, (0, 0, 0)),
            )
        )
        self._current_brightness = 0
        self._is_off = True

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._send(protocol.build_switch_profile_report(self._profile_id))
        self._send(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_brightness = level
        self._is_off = False

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        if rgb == (0, 0, 0) or int(brightness) <= 0:
            self.turn_off()
            return
        groups = protocol.build_uniform_static_groups_for_leds(self._led_ids, rgb)
        self._apply_groups(groups, brightness=brightness)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del color_map, brightness, enable_user_mode
        raise RuntimeError(f"ITE 8258 chassis {self._zone_name} zone does not support per-key coloring")

    def set_effect(self, effect_data) -> None:
        del effect_data
        raise RuntimeError(f"ITE 8258 chassis {self._zone_name} zone does not support hardware effects")

    def close(self) -> None:
        transport = self._transport
        if transport is not None:
            self._transport = None
            close_fn = getattr(transport, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except (OSError, RuntimeError, ValueError):
                    _logger.debug(
                        "Error closing ITE 8258 chassis %s zone HID transport",
                        self._zone_name,
                        exc_info=True,
                    )


# Clarification: Ite8258ChassisZoneDevice is currently hardcoded for the Lenovo
# Legion Pro 7 Gen10 zone layout (logo, neon, vent).  If a new 0xc197-or-other
# laptop uses the same chip with different zones, the zone_key -> led_ids mapping
# in backend.py must be updated or moved into a product-variant registry.
