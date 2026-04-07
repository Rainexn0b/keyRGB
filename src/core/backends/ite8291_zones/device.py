from __future__ import annotations

from collections.abc import Callable, Sequence

from . import protocol

FeatureReportWriter = Callable[[bytes], int | None]


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


class Ite8291ZonesKeyboardDevice:
    """4-zone HID wrapper for the legacy ce00 bcdDevice 0x0002 firmware path."""

    def __init__(self, send_feature_report: FeatureReportWriter, *, current_brightness: int = 0) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)
        self._zone_colors: list[tuple[int, int, int]] = [(0, 0, 0) for _ in range(protocol.NUM_ZONES)]
        self._is_off = self._current_brightness <= 0

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8291 zone feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._send(report)

    def _apply_current_state(self) -> None:
        if self._current_brightness <= 0:
            self.turn_off()
            return

        self._send(protocol.build_zone_enable_report())
        for zone_index, color in enumerate(self._zone_colors):
            self._send(protocol.build_zone_color_report(zone_index, color))
        self._send(protocol.build_commit_state_report(self._current_brightness))
        self._is_off = False

    def turn_off(self) -> None:
        self._write_reports(protocol.build_turn_off_reports())
        self._current_brightness = 0
        self._is_off = True

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def set_brightness(self, brightness: int) -> None:
        self._current_brightness = protocol.clamp_ui_brightness(brightness)
        self._apply_current_state()

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        self._zone_colors = [rgb for _ in range(protocol.NUM_ZONES)]
        self._current_brightness = protocol.clamp_ui_brightness(brightness)
        self._apply_current_state()

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del enable_user_mode
        if not color_map:
            self.set_color((0, 0, 0), brightness=brightness)
            return

        red = green = blue = count = 0
        for color in color_map.values():
            r, g, b = _coerce_rgb(color)
            red += r
            green += g
            blue += b
            count += 1

        if count <= 0:
            self.set_color((0, 0, 0), brightness=brightness)
            return

        self.set_color((red // count, green // count, blue // count), brightness=brightness)

    def set_effect(self, effect_data) -> None:
        del effect_data
        return