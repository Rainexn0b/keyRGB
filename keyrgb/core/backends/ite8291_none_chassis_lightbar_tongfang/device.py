from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from . import protocol

_logger = logging.getLogger(__name__)

FeatureReportWriter = Callable[[bytes], int]
OutputReportWriter = Callable[[bytes], int | None]


def _clamp_channel(value: object) -> int:
    if isinstance(value, bool):
        return protocol.clamp_channel(int(value))
    if isinstance(value, (int, float)):
        return protocol.clamp_channel(int(value))
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return protocol.clamp_channel(int(value))
        except (TypeError, ValueError):
            raise ValueError(f"invalid color channel: {value!r}") from None
    raise ValueError(f"invalid color channel: {value!r}")


def _average_color(color_map: object, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Collapse a per-key color map to one uniform average for software effects."""
    values: Iterable[object]
    if isinstance(color_map, dict):
        values = color_map.values()
    elif isinstance(color_map, (list, tuple)):
        values = color_map
    else:
        return fallback

    red_total = green_total = blue_total = 0
    count = 0
    for item in values:
        try:
            red, green, blue = item
        except (TypeError, ValueError):
            continue
        try:
            red_total += _clamp_channel(red)
            green_total += _clamp_channel(green)
            blue_total += _clamp_channel(blue)
        except (TypeError, ValueError):
            continue
        count += 1

    if count <= 0:
        return fallback
    return (
        round(red_total / count),
        round(green_total / count),
        round(blue_total / count),
    )


class Ite8291TongfangLightbarDevice:
    """Uniform lightbar device for 048d:6005 (Tongfang ITE 8291 lightbar).

    Raw RGB is preserved as-is; brightness is the controller mode
    brightness and is never software-scaled into the RGB channels. No
    persistence/save report is ever sent by this device.
    """

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        write_output_report: OutputReportWriter,
        *,
        product_id: int = protocol.DEFAULT_PRODUCT_ID,
        current_brightness: int = 50,
        transport: object | None = None,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")
        if not callable(write_output_report):
            raise TypeError("write_output_report must be callable")

        self._send_feature_report = send_feature_report
        self._write_output_report = write_output_report
        self._transport = transport
        self._product_id = protocol.normalize_product_id(product_id)
        self._brightness = protocol.clamp_brightness(current_brightness)
        self._current_color = (255, 255, 255)
        self._is_off = self._brightness <= 0

    def _write_feature(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result) < 0:
            raise OSError("Could not send ITE 8291 Tongfang lightbar feature report")

    def _write_features(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._write_feature(report)

    def _write_output(self, report: bytes) -> None:
        result = self._write_output_report(bytes(report))
        if result is not None and int(result) < 0:
            raise OSError("Could not send ITE 8291 Tongfang lightbar output report")

    def _send_direct_uniform(self, color: tuple[int, int, int], *, brightness: int) -> None:
        """Direct uniform sequence: mode, begin, 65-byte frame, commit."""
        self._write_feature(protocol.build_direct_mode_report(brightness=brightness))
        self._write_feature(protocol.build_begin_report())
        self._write_output(protocol.build_direct_frame(color))
        self._write_feature(protocol.build_commit_report())

    def _normalize_effect_name(self, effect_data: object) -> str:
        if isinstance(effect_data, str):
            return effect_data.strip().lower().replace(" ", "_")
        if isinstance(effect_data, dict):
            name = effect_data.get("name") or effect_data.get("effect")
            return str(name or "").strip().lower().replace(" ", "_")
        return ""

    def turn_off(self) -> None:
        self._write_feature(protocol.build_off_report())
        self._is_off = True
        self._brightness = 0

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._send_direct_uniform(self._current_color, brightness=level)
        self._brightness = level
        self._is_off = False

    def set_color(self, color, *, brightness: int):
        raw = tuple(_clamp_channel(channel) for channel in color)
        if len(raw) != 3:
            raise ValueError("color must be an RGB 3-tuple")
        level = protocol.clamp_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._send_direct_uniform(raw, brightness=level)
        self._current_color = raw
        self._brightness = level
        self._is_off = False

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True) -> None:
        """Collapse per-key colors to their uniform average (software effects)."""
        del enable_user_mode
        average = _average_color(color_map, fallback=self._current_color)
        self.set_color(average, brightness=brightness)

    def set_effect(self, effect_data) -> None:
        effect_name = self._normalize_effect_name(effect_data)
        if effect_name in {"breathing", "breathe", "breathing_color"}:
            mode = protocol.MODE_BREATHING
        elif effect_name == "wave":
            mode = protocol.MODE_WAVE
        elif effect_name in {"raindrops", "raindrop", "rain_drops", "rain_drop"}:
            mode = protocol.MODE_RAINDROPS
        else:
            raise RuntimeError(f"Unsupported ITE 8291 Tongfang lightbar effect: {effect_name or effect_data!r}")

        effect_dict: dict[str, Any] = effect_data if isinstance(effect_data, dict) else {}
        brightness = protocol.clamp_brightness(effect_dict.get("brightness", self._brightness))
        speed = protocol.clamp_speed(effect_dict.get("speed", 5))
        if brightness <= 0:
            self.turn_off()
            return

        color = effect_dict.get("color", self._current_color)
        raw = tuple(_clamp_channel(channel) for channel in color)
        if len(raw) != 3:
            raise ValueError("effect color must be an RGB 3-tuple")

        self._write_feature(protocol.build_mode_report(mode=mode, brightness=brightness, speed=speed))
        self._write_features(protocol.build_effect_color_reports(raw))
        self._current_color = raw
        self._brightness = brightness
        self._is_off = False

    def close(self) -> None:
        """Release the HID transport if one was provided (best effort)."""
        transport = self._transport
        if transport is not None:
            self._transport = None
            close_fn = getattr(transport, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except (OSError, RuntimeError, ValueError):
                    _logger.debug("Error closing ITE 8291 Tongfang lightbar transport", exc_info=True)
