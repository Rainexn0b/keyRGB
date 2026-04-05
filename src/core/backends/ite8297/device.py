from __future__ import annotations

from typing import Callable

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


class Ite8297KeyboardDevice:
    """Minimal device wrapper for the public ITE 8297 uniform-color HID path."""

    def __init__(self, send_feature_report: FeatureReportWriter, *, current_brightness: int = 50) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._current_color = (0, 0, 0)
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if result == -1:
            raise OSError("Could not send ITE 8297 feature report")

    def _apply_current_state(self) -> None:
        scaled = protocol.scale_color_for_brightness(self._current_color, self._current_brightness)
        self._send(protocol.build_uniform_color_report(scaled))

    def turn_off(self) -> None:
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self._current_brightness <= 0

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def set_brightness(self, brightness: int) -> None:
        self._current_brightness = protocol.clamp_ui_brightness(brightness)
        self._apply_current_state()

    def set_color(self, color, *, brightness: int):
        self._current_color = _coerce_rgb(color)
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

    def set_effect(self, effect_data: object) -> None:
        del effect_data
        return
