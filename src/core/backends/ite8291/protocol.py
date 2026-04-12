from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import SupportsIndex, SupportsInt, cast

HIDRAW_PATH_ENV = "KEYRGB_ITE8291_HIDRAW_PATH"

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x6004, 0x6008, 0x600B, 0xCE00)

NUM_ROWS = 6
NUM_COLS = 21

CONTROL_REPORT_SIZE = 8
ROW_DATA_PADDING = 2
ROW_DATA_LENGTH = ROW_DATA_PADDING + (NUM_COLS * 3)

ROW_BLUE_OFFSET = ROW_DATA_PADDING + (NUM_COLS * 0)
ROW_GREEN_OFFSET = ROW_DATA_PADDING + (NUM_COLS * 1)
ROW_RED_OFFSET = ROW_DATA_PADDING + (NUM_COLS * 2)

UI_BRIGHTNESS_MAX = 50
USER_MODE_CODE = 0x33

_ZONE_ONLY_FW_BY_PID: dict[int, frozenset[int]] = {
    0xCE00: frozenset({0x0002}),
}

IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def clamp_channel(value: object) -> int:
    return max(0, min(255, _coerce_int(value)))


def clamp_ui_brightness(value: object) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, _coerce_int(value)))


def _coerce_rgb(color: object) -> tuple[int, int, int]:
    try:
        red, green, blue = cast(Iterable[object], color)
    except (TypeError, ValueError) as exc:
        raise ValueError("row colors must be RGB 3-tuples") from exc
    return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))


def firmware_requires_zone_mode(product_id: int, bcd_device: int | None) -> bool:
    if bcd_device is None:
        return False
    return int(bcd_device) in _ZONE_ONLY_FW_BY_PID.get(int(product_id), frozenset())


def build_turn_off_report() -> bytes:
    return bytes((0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))


def build_user_mode_report(brightness: int, *, save: bool = False) -> bytes:
    return bytes(
        (
            0x08,
            0x02,
            USER_MODE_CODE,
            0x00,
            clamp_ui_brightness(brightness),
            0x00,
            0x00,
            0x01 if save else 0x00,
        )
    )


def build_row_announce_report(row: int) -> bytes:
    row_idx = int(row)
    if row_idx < 0 or row_idx >= NUM_ROWS:
        raise ValueError(f"row must be between 0 and {NUM_ROWS - 1} inclusive")
    return bytes((0x16, 0x00, row_idx, 0x00, 0x00, 0x00, 0x00, 0x00))


def build_row_data_report(colors: Sequence[object]) -> bytes:
    if len(colors) != NUM_COLS:
        raise ValueError(f"row must contain exactly {NUM_COLS} colors")

    payload = bytearray(ROW_DATA_LENGTH)
    for col, color in enumerate(colors):
        red, green, blue = _coerce_rgb(color)

        payload[ROW_BLUE_OFFSET + col] = clamp_channel(blue)
        payload[ROW_GREEN_OFFSET + col] = clamp_channel(green)
        payload[ROW_RED_OFFSET + col] = clamp_channel(red)

    return bytes(payload)
