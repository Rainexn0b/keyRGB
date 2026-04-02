from __future__ import annotations

from typing import Any, Callable

from . import protocol

FeatureReportWriter = Callable[[bytes], int | None]


def _clamp_ui_brightness(value: int) -> int:
    return max(0, min(protocol.UI_BRIGHTNESS_MAX, int(value)))


def _coerce_rgb(color) -> tuple[int, int, int]:
    try:
        red, green, blue = color
    except Exception as exc:
        raise ValueError("color must be an RGB 3-tuple") from exc

    return (
        protocol.clamp_channel(red),
        protocol.clamp_channel(green),
        protocol.clamp_channel(blue),
    )


def _coerce_led_id(key_id: Any) -> int:
    if isinstance(key_id, tuple):
        if len(key_id) != 2:
            raise ValueError("tuple key ids must be (row, col)")
        row, col = key_id
        return protocol.led_id_from_row_col(int(row), int(col))
    return int(key_id) & 0xFF


def _coerce_effect_value(effect_data: Any) -> protocol.Ite8910Effect | int | str:
    if isinstance(effect_data, dict):
        if "index" in effect_data:
            effect_value = effect_data["index"]
        elif "effect" in effect_data:
            effect_value = effect_data["effect"]
        elif "name" in effect_data:
            effect_value = effect_data["name"]
        else:
            raise ValueError("ITE 8910 effect dict must contain 'index', 'effect', or 'name'")
    elif isinstance(effect_data, (list, tuple)) and len(effect_data) > 0:
        effect_value = effect_data[0]
    else:
        effect_value = effect_data

    if isinstance(effect_value, (protocol.Ite8910Effect, int, str)):
        return effect_value

    raise ValueError("ITE 8910 effect value must be an effect enum, int, or string")


def _coerce_effect_payload_speed(value: Any) -> int:
    return protocol.raw_speed_from_effect_speed(int(value))


class Ite8910KeyboardDevice:
    """Callback-driven device wrapper for the translated ITE 8910 protocol.

    The writer callback remains injectable so protocol behavior can be unit-
    tested independently from the Linux `hidraw` transport.
    """

    keyrgb_hw_speed_policy = "direct"
    keyrgb_per_key_mode_policy = "init_once"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        *,
        current_brightness: int = 0,
        current_speed_raw: int = 0,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._state = protocol.Ite8910ProtocolState(
            current_brightness_raw=protocol.raw_brightness_from_ui(current_brightness),
            current_speed_raw=protocol.clamp_raw_speed(current_speed_raw),
        )
        self._current_brightness = _clamp_ui_brightness(current_brightness)

    @property
    def current_brightness_raw(self) -> int:
        return int(self._state.current_brightness_raw)

    @property
    def current_speed_raw(self) -> int:
        return int(self._state.current_speed_raw)

    def _send(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if result == -1:
            raise OSError("Could not send ITE 8910 feature report")

    def turn_off(self) -> None:
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self._current_brightness <= 0

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def set_brightness_and_speed_raw(self, brightness_raw: int, speed_raw: int) -> None:
        self._send(self._state.set_brightness_and_speed_raw(brightness_raw, speed_raw))
        self._current_brightness = protocol.ui_brightness_from_raw(self._state.current_brightness_raw)

    def set_brightness_raw(self, brightness_raw: int) -> None:
        self._send(self._state.set_brightness_raw(brightness_raw))
        self._current_brightness = protocol.ui_brightness_from_raw(self._state.current_brightness_raw)

    def set_speed_raw(self, speed_raw: int) -> None:
        self._send(self._state.set_speed_raw(speed_raw))

    def set_brightness(self, brightness: int) -> None:
        requested = _clamp_ui_brightness(brightness)
        self._send(self._state.set_brightness_raw(protocol.raw_brightness_from_ui(requested)))
        self._current_brightness = requested

    def reset(self) -> None:
        self._send(self._state.reset())
        for led_id in protocol.iter_known_led_ids():
            self._send(self._state.set_led_color(led_id, (0, 0, 0)))

    def set_led_color_by_id(self, led_id: int, color) -> None:
        self._send(self._state.set_led_color(int(led_id), _coerce_rgb(color)))

    def set_matrix_color(self, row: int, col: int, color) -> None:
        self.set_led_color_by_id(protocol.led_id_from_row_col(row, col), color)

    def set_effect_index(
        self,
        effect: protocol.Ite8910Effect | int | str,
        colors: list[tuple[int, int, int]] | None = None,
        direction: str | None = None,
    ) -> None:
        for report in self._state.set_effect(effect, colors, direction):
            self._send(report)

    def enable_user_mode(self, *, brightness: int, save: bool = False) -> None:
        del save
        self.reset()
        self.set_brightness(brightness)

    def set_palette_color(self, _slot: int, _color) -> None:
        # The public ITE 829x protocol uses direct RGB writes rather than a
        # programmable palette table.
        return

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        self.enable_user_mode(brightness=brightness, save=False)
        for led_id in protocol.iter_known_led_ids():
            self.set_led_color_by_id(led_id, rgb)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        if enable_user_mode:
            self.enable_user_mode(brightness=brightness, save=False)

        for key_id, color in (color_map or {}).items():
            self.set_led_color_by_id(_coerce_led_id(key_id), color)

    def set_effect(self, effect_data) -> None:
        direction = None
        colors = None

        if isinstance(effect_data, dict):
            brightness = effect_data.get("brightness", None)
            speed = effect_data.get("speed", None)
            direction = effect_data.get("direction", None)
            color = effect_data.get("color", None)

            if brightness is not None or speed is not None:
                brightness_raw = self.current_brightness_raw
                speed_raw = self.current_speed_raw

                if brightness is not None:
                    brightness_raw = protocol.raw_brightness_from_ui(int(brightness))
                if speed is not None:
                    speed_raw = _coerce_effect_payload_speed(speed)

                self.set_brightness_and_speed_raw(brightness_raw, speed_raw)

            if color is not None:
                colors = [_coerce_rgb(color)]

        self.set_effect_index(_coerce_effect_value(effect_data), colors=colors, direction=direction)
