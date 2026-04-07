from __future__ import annotations

from collections.abc import Callable

from . import protocol

FeatureReportWriter = Callable[[bytes], int | None]
OutputReportWriter = Callable[[bytes], int | None]
_ColorMatrix = list[list[tuple[int, int, int]]]


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


def _blank_matrix() -> _ColorMatrix:
    return [[(0, 0, 0) for _ in range(protocol.NUM_COLS)] for _ in range(protocol.NUM_ROWS)]


def _coerce_row_col(key_id: object) -> tuple[int, int] | None:
    if isinstance(key_id, tuple):
        if len(key_id) != 2:
            raise ValueError("tuple key ids must be (row, col)")
        row, col = key_id
    elif isinstance(key_id, str) and "," in key_id:
        row_text, col_text = key_id.split(",", 1)
        try:
            row = int(row_text.strip())
            col = int(col_text.strip())
        except ValueError:
            return None
    else:
        return None

    row_idx = int(row)
    col_idx = int(col)
    if row_idx < 0 or row_idx >= protocol.NUM_ROWS:
        return None
    if col_idx < 0 or col_idx >= protocol.NUM_COLS:
        return None
    return row_idx, col_idx


class Ite8291KeyboardDevice:
    """Native HID wrapper for the 6x21 ITE 8291 per-key row protocol."""

    keyrgb_hw_speed_policy = "inverted"
    keyrgb_per_key_mode_policy = "reassert_every_frame"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        write_output_report: OutputReportWriter,
        *,
        current_brightness: int = 0,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")
        if not callable(write_output_report):
            raise TypeError("write_output_report must be callable")

        self._send_feature_report = send_feature_report
        self._write_output_report = write_output_report
        self._current_brightness = protocol.clamp_ui_brightness(current_brightness)
        self._current_matrix = _blank_matrix()
        self._is_off = self._current_brightness <= 0

    def _send_feature(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8291 feature report")

    def _send_output(self, report: bytes) -> None:
        result = self._write_output_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8291 output report")

    def _write_matrix_rows(self) -> None:
        for row_idx, colors in enumerate(self._current_matrix):
            self._send_feature(protocol.build_row_announce_report(row_idx))
            self._send_output(protocol.build_row_data_report(colors))

    def turn_off(self) -> None:
        self._send_feature(protocol.build_turn_off_report())
        self._current_brightness = 0
        self._is_off = True

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._current_brightness)

    def enable_user_mode(self, *, brightness: int, save: bool = False) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return
        self._send_feature(protocol.build_user_mode_report(level, save=save))
        self._current_brightness = level
        self._is_off = False

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return
        self.enable_user_mode(brightness=level, save=False)
        self._write_matrix_rows()

    def set_color(self, color, *, brightness: int):
        rgb = _coerce_rgb(color)
        self._current_matrix = [[rgb for _ in range(protocol.NUM_COLS)] for _ in range(protocol.NUM_ROWS)]
        self.enable_user_mode(brightness=brightness, save=False)
        self._write_matrix_rows()

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        matrix = _blank_matrix()
        for key_id, color in dict(color_map or {}).items():
            row_col = _coerce_row_col(key_id)
            if row_col is None:
                continue
            row, col = row_col
            matrix[row][col] = _coerce_rgb(color)

        self._current_matrix = matrix
        if enable_user_mode:
            self.enable_user_mode(brightness=brightness, save=False)
        else:
            level = protocol.clamp_ui_brightness(brightness)
            if level <= 0:
                self.turn_off()
                return
            self._current_brightness = level
            self._is_off = False

        self._write_matrix_rows()

    def set_effect(self, effect_data) -> None:
        del effect_data
        return