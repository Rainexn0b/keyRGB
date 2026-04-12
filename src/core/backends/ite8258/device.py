from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import SupportsIndex, SupportsInt, cast

from . import protocol

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


def _normalize_effect_name(effect_data: object) -> str:
    if isinstance(effect_data, dict):
        effect_value = effect_data.get("name", effect_data.get("effect", ""))
    elif isinstance(effect_data, (list, tuple)) and effect_data:
        effect_value = effect_data[0]
    else:
        effect_value = effect_data
    return str(effect_value or "").strip().lower().replace(" ", "_")


class Ite8258KeyboardDevice:
    """24-zone keyboard wrapper for the ITE 8258 Legion Gen 10 path."""

    keyrgb_hw_speed_policy = "direct"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        *,
        profile_id: int = protocol.DEFAULT_PROFILE_ID,
        current_brightness: int = protocol.UI_BRIGHTNESS_MAX,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._profile_id = int(profile_id) & 0xFF
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)
        self._is_off = self._current_brightness <= 0

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8258 feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._send(report)

    def _apply_groups(self, groups: Sequence[protocol.Ite8258Group], *, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._write_reports(protocol.build_save_profile_reports(self._profile_id, groups))
        self._send(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_brightness = level
        self._is_off = False

    def turn_off(self) -> None:
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
            led_colors[_coerce_led_id(key_id)] = _coerce_rgb(color)

        zone_colors = protocol.build_static_zone_map(led_colors)
        if all(color == (0, 0, 0) for color in zone_colors):
            self.turn_off()
            return

        self._apply_groups(protocol.build_static_groups(zone_colors), brightness=brightness)

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
