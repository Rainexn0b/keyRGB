from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import SupportsIndex, SupportsInt, cast

from . import protocol

FeatureReportWriter = Callable[[bytes], int | None]
IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


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


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def _normalize_effect_name(effect_data: object) -> str:
    if isinstance(effect_data, Mapping):
        effect_value = effect_data.get("name", effect_data.get("effect", ""))
    elif isinstance(effect_data, (list, tuple)) and effect_data:
        effect_value = effect_data[0]
    else:
        effect_value = effect_data
    return protocol.normalize_effect_name(effect_value)


def _coerce_zone_index(key_id: object) -> int | None:
    if isinstance(key_id, tuple):
        if len(key_id) != 2:
            return None
        row, col = key_id
        if int(row) != 0:
            return None
        zone_index = int(col)
    else:
        try:
            zone_index = _coerce_int(key_id)
        except (TypeError, ValueError):
            return None

    if 0 <= zone_index < protocol.NUM_ZONES:
        return zone_index
    return None


class Ite8295ZonesKeyboardDevice:
    """4-zone Lenovo/ITE 8295 keyboard wrapper for the c963 hidraw path."""

    keyrgb_hw_speed_policy = "direct"

    def __init__(self, send_feature_report: FeatureReportWriter, *, current_brightness: int = 0) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._zone_colors: list[tuple[int, int, int]] = [(0, 0, 0) for _ in range(protocol.NUM_ZONES)]
        self._brightness = protocol.clamp_ui_brightness(current_brightness)
        self._effect_name = "static"
        self._speed = protocol.raw_speed_from_ui(protocol.UI_SPEED_MAX // 2)
        self._direction = "right"
        self._is_off = self._brightness <= 0

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8295 4-zone feature report")

    def _effective_zone_colors(self) -> tuple[tuple[int, int, int], ...]:
        if any(color != (0, 0, 0) for color in self._zone_colors):
            return tuple(self._zone_colors)
        return protocol.uniform_zone_colors((255, 255, 255))

    def _build_current_report(self) -> bytes:
        raw_brightness = protocol.raw_brightness_from_ui(self._brightness)
        if raw_brightness <= 0:
            return protocol.build_turn_off_report()

        zone_colors = tuple(self._zone_colors)
        if self._effect_name == "static":
            return protocol.build_static_report(zone_colors, brightness=raw_brightness)
        if self._effect_name == "breathing":
            return protocol.build_breathing_report(zone_colors, brightness=raw_brightness, speed=self._speed)
        if self._effect_name == "wave":
            return protocol.build_wave_report(
                self._effective_zone_colors(),
                brightness=raw_brightness,
                speed=self._speed,
                direction=self._direction,
            )
        if self._effect_name == "spectrum_cycle":
            return protocol.build_smooth_report(
                self._effective_zone_colors(),
                brightness=raw_brightness,
                speed=self._speed,
            )
        raise RuntimeError(f"Unsupported ITE 8295 effect '{self._effect_name}'")

    def _apply_current_state(self) -> None:
        self._send(self._build_current_report())
        self._is_off = self._brightness <= 0

    def _average_color(self, color_map: Mapping[object, object]) -> tuple[int, int, int]:
        red = green = blue = count = 0
        for color in color_map.values():
            r, g, b = _coerce_rgb(color)
            red += r
            green += g
            blue += b
            count += 1
        if count <= 0:
            return (0, 0, 0)
        return (red // count, green // count, blue // count)

    def turn_off(self) -> None:
        self._send(protocol.build_turn_off_report())
        self._brightness = 0
        self._is_off = True

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._brightness = level
        self._apply_current_state()

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        level = protocol.clamp_ui_brightness(brightness)
        self._zone_colors = [rgb for _ in range(protocol.NUM_ZONES)]
        self._effect_name = "static"
        self._brightness = level
        if level <= 0 or rgb == (0, 0, 0):
            self.turn_off()
            return
        self._apply_current_state()

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del enable_user_mode
        if not isinstance(color_map, Mapping) or not color_map:
            self.turn_off()
            return

        level = protocol.clamp_ui_brightness(brightness)
        zone_colors = list(self._zone_colors)
        parsed_all = True
        for key_id, color in color_map.items():
            zone_index = _coerce_zone_index(key_id)
            if zone_index is None:
                parsed_all = False
                break
            zone_colors[zone_index] = _coerce_rgb(color)

        if not parsed_all:
            avg = self._average_color(color_map)
            self.set_color(avg, brightness=brightness)
            return

        self._zone_colors = zone_colors
        self._effect_name = "static"
        self._brightness = level
        if level <= 0 or all(color == (0, 0, 0) for color in self._zone_colors):
            self.turn_off()
            return
        self._apply_current_state()

    def set_effect(self, effect_data) -> None:
        effect_name = _normalize_effect_name(effect_data)
        effect_dict = effect_data if isinstance(effect_data, Mapping) else {}

        normalized = {
            "breathe": "breathing",
            "breathing_color": "breathing",
            "rainbow_wave": "wave",
            "smooth": "spectrum_cycle",
        }.get(effect_name, effect_name)

        if normalized not in {"breathing", "wave", "spectrum_cycle"}:
            raise RuntimeError(f"ITE 8295 does not support hardware effect '{effect_name}'")

        level = protocol.clamp_ui_brightness(effect_dict.get("brightness", self._brightness or protocol.UI_BRIGHTNESS_MAX))
        if level <= 0:
            self.turn_off()
            return

        self._brightness = level
        self._speed = protocol.raw_speed_from_ui(effect_dict.get("speed", protocol.UI_SPEED_MAX // 2))
        self._direction = str(effect_dict.get("direction", self._direction or "right"))
        self._effect_name = normalized

        color = effect_dict.get("color", None)
        if normalized == "breathing":
            if color is None:
                if any(zone != (0, 0, 0) for zone in self._zone_colors):
                    color = self._zone_colors[0]
                else:
                    color = (255, 255, 255)
            rgb = _coerce_rgb(color)
            self._zone_colors = [rgb for _ in range(protocol.NUM_ZONES)]

        self._apply_current_state()