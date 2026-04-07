from __future__ import annotations

from collections.abc import Callable

from . import protocol

ControlWriter = Callable[[bytes], int | None]
ControlReader = Callable[[int], bytes | bytearray | list[int]]
RowWriter = Callable[[bytes], int | None]


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


def _coerce_effect_payload(effect_data: object) -> tuple[int, ...]:
    if isinstance(effect_data, dict):
        name = effect_data.get("name")
        if isinstance(name, str) and name in protocol.effects:
            kwargs = {
                key: value
                for key, value in effect_data.items()
                if key in {"speed", "brightness", "color", "direction", "reactive", "save"}
            }
            built = protocol.effects[name](**kwargs)
            return tuple(int(value) for value in built)

        effect_value = effect_data.get("effect", effect_data.get("index"))
        if effect_value is None:
            raise ValueError("effect dict must contain 'effect', 'index', or 'name'")
        return (
            int(effect_value),
            int(effect_data.get("speed", 0)),
            int(effect_data.get("brightness", 0)),
            int(effect_data.get("color", 0)),
            int(effect_data.get("direction", effect_data.get("reactive", 0))),
            int(effect_data.get("save", 0)),
        )

    if isinstance(effect_data, (list, tuple)):
        payload = tuple(int(value) for value in effect_data)
        if len(payload) > 6:
            raise ValueError("effect payload must contain at most 6 values")
        return payload

    raise ValueError("effect_data must be a dict, list, or tuple")


class Ite8291r3KeyboardDevice:
    keyrgb_hw_speed_policy = "inverted"
    keyrgb_per_key_mode_policy = "reassert_every_frame"

    def __init__(
        self,
        send_control_report: ControlWriter,
        read_control_report: ControlReader,
        write_row_data: RowWriter,
    ) -> None:
        if not callable(send_control_report):
            raise TypeError("send_control_report must be callable")
        if not callable(read_control_report):
            raise TypeError("read_control_report must be callable")
        if not callable(write_row_data):
            raise TypeError("write_row_data must be callable")

        self._send_control_report = send_control_report
        self._read_control_report = read_control_report
        self._write_row_data = write_row_data

    def _send_control(self, report: bytes) -> None:
        result = self._send_control_report(bytes(report))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8291r3 control report")

    def _read_control(self, length: int) -> bytes:
        data = self._read_control_report(int(length))
        return bytes(data)

    def _write_row(self, row_data: bytes) -> None:
        result = self._write_row_data(bytes(row_data))
        if int(result or 0) < 0:
            raise OSError("Could not send ITE 8291r3 row data")

    def get_fw_version(self) -> tuple[int, int, int, int]:
        self._send_control(protocol.build_get_fw_version_report())
        buf = self._read_control(8)
        return (int(buf[1]), int(buf[2]), int(buf[3]), int(buf[4]))

    def get_effect(self) -> list[int]:
        self._send_control(protocol.build_get_effect_report())
        return [int(value) for value in self._read_control(8)[2:]]

    def _set_row_index(self, row_idx: int) -> None:
        self._send_control(protocol.build_set_row_index_report(row_idx))

    def _set_effect_impl(
        self,
        *,
        control: int,
        effect: int = 0,
        speed: int = 0,
        brightness: int = 0,
        color: int = 0,
        direction_or_reactive: int = 0,
        save: int = 0,
    ) -> None:
        self._send_control(
            protocol.build_set_effect_report(
                control=control,
                effect=effect,
                speed=speed,
                brightness=brightness,
                color=color,
                direction_or_reactive=direction_or_reactive,
                save=save,
            )
        )

    def set_effect(self, effect_data) -> None:
        payload = _coerce_effect_payload(effect_data)
        padded = list(payload[:6])
        if len(padded) < 6:
            padded.extend([0] * (6 - len(padded)))
        self._set_effect_impl(
            control=0x02,
            effect=int(padded[0]),
            speed=int(padded[1]),
            brightness=int(padded[2]),
            color=int(padded[3]),
            direction_or_reactive=int(padded[4]),
            save=int(padded[5]),
        )

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        self._send_control(protocol.build_set_brightness_report(level))

    def freeze(self) -> None:
        effect = self.get_effect()
        if len(effect) > protocol.EffectAttrs.SPEED:
            effect[protocol.EffectAttrs.SPEED] = 11
        self.set_effect(effect)

    def turn_off(self) -> None:
        self._set_effect_impl(control=0x01)

    def is_off(self) -> bool:
        self._send_control(protocol.build_get_effect_report())
        return self._read_control(8)[1] == 0x01

    def get_brightness(self) -> int:
        effect = self.get_effect()
        return int(effect[protocol.EffectAttrs.BRIGHTNESS])

    def enable_user_mode(self, *, brightness: int | None = None, save: bool = False) -> None:
        level = self.get_brightness() if brightness is None else protocol.clamp_ui_brightness(brightness)
        self.set_effect((protocol.USER_MODE_EFFECT, 0x00, level, 0x00, 0x00, 0x01 if save else 0x00))

    def set_color(self, color, *, brightness: int, save: bool = False):
        rgb = _coerce_rgb(color)
        self.enable_user_mode(brightness=brightness, save=save)
        row_report = protocol.build_uniform_row_data_report(rgb)
        for row_idx in range(protocol.NUM_ROWS):
            self._set_row_index(row_idx)
            self._write_row(row_report)

    def set_palette_color(self, slot: int, color) -> None:
        if not (1 <= int(slot) <= 7):
            raise ValueError("palette color index must be between 1 and 7 (inclusive)")
        self._send_control(protocol.build_set_palette_color_report(int(slot), _coerce_rgb(color)))

    def restore_default_palette(self) -> None:
        for slot, color in sorted(protocol.DEFAULT_PALETTE.items()):
            self.set_palette_color(int(slot), color)

    def test_pattern(self, shift: int = 0, *, brightness: int, save: bool = False) -> None:
        colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
        self.enable_user_mode(brightness=brightness, save=save)

        for row_idx in range(protocol.NUM_ROWS):
            row_colors = [(0, 0, 0) for _ in range(protocol.NUM_COLS)]
            for col in range(0, protocol.NUM_COLS, 3):
                for offset in range(3):
                    if col + offset >= protocol.NUM_COLS:
                        continue
                    row_colors[col + offset] = colors[(offset + row_idx + int(shift)) % 3]
            self._set_row_index(row_idx)
            self._write_row(protocol.build_row_data_report(row_colors))

    def set_key_colors(
        self,
        color_map=None,
        *,
        brightness: int,
        save: bool = False,
        enable_user_mode: bool = True,
    ):
        rows: list[list[tuple[int, int, int]]] = [
            [(0, 0, 0) for _ in range(protocol.NUM_COLS)]
            for _ in range(protocol.NUM_ROWS)
        ]

        for key_id, color in dict(color_map or {}).items():
            row_col = _coerce_row_col(key_id)
            if row_col is None:
                continue
            row_idx, col_idx = row_col
            rows[row_idx][col_idx] = _coerce_rgb(color)

        if enable_user_mode or save:
            self.enable_user_mode(brightness=brightness, save=save)

        for row_idx, row_colors in enumerate(rows):
            self._set_row_index(row_idx)
            self._write_row(protocol.build_row_data_report(row_colors))