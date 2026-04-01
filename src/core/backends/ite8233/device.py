from __future__ import annotations

from collections.abc import Callable, Sequence

from . import protocol

FeatureReportWriter = Callable[[bytes], int]


class Ite8233LightbarDevice:
    """Minimal single-zone lightbar device for the ITE 8233 / 0x7001 path."""

    def __init__(self, send_feature_report: FeatureReportWriter, *, current_brightness: int = 50) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._brightness = protocol.clamp_ui_brightness(current_brightness)
        self._current_color = (255, 255, 255)
        self._is_off = self._brightness <= 0

    def _write_report(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result) < 0:
            raise OSError("Could not send ITE 8233 feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._write_report(report)

    def _raise_unimplemented(self) -> None:
        raise RuntimeError(
            "ITE 8233 lightbar protocol is not implemented yet; collect protocol dumps before enabling this backend"
        )

    def turn_off(self) -> None:
        self._write_reports(protocol.build_turn_off_reports())
        self._is_off = True
        self._brightness = 0

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._write_report(protocol.build_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._brightness = level
        self._is_off = False

    def set_color(self, color, *, brightness: int):
        scaled = protocol.scale_color_for_brightness(color, brightness)
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._write_report(protocol.build_uniform_color_report(scaled))
        self._write_report(protocol.build_brightness_report(protocol.raw_brightness_from_ui(level)))
        self._current_color = tuple(int(channel) for channel in color)
        self._brightness = level
        self._is_off = False

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del color_map, brightness, enable_user_mode
        self._raise_unimplemented()

    def set_effect(self, effect_data) -> None:
        del effect_data
        self._raise_unimplemented()