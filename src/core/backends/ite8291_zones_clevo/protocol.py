from __future__ import annotations

from collections.abc import Iterable
from typing import SupportsIndex, SupportsInt, cast

HIDRAW_PATH_ENV = "KEYRGB_ITE8291_ZONES_HIDRAW_PATH"

VENDOR_ID = 0x048D
PRODUCT_ID = 0xCE00
REQUIRED_BCD_DEVICE = 0x0002
NUM_ZONES = 4
UI_BRIGHTNESS_MAX = 50
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
        raise ValueError("color must be an RGB 3-tuple") from exc
    return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))


def build_zone_enable_report() -> bytes:
    return bytes((0x1A, 0x00, 0x01, 0x04, 0x00, 0x00, 0x00, 0x01))


def build_zone_disable_report() -> bytes:
    return bytes((0x1A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01))


def build_zone_color_report(zone_index: int, color) -> bytes:
    zone = int(zone_index)
    if zone < 0 or zone >= NUM_ZONES:
        raise ValueError(f"zone_index must be between 0 and {NUM_ZONES - 1} inclusive")

    red, green, blue = _coerce_rgb(color)

    return bytes((0x14, 0x00, zone + 1, clamp_channel(red), clamp_channel(green), clamp_channel(blue), 0x00, 0x00))


def build_commit_state_report(brightness: int) -> bytes:
    return bytes((0x08, 0x02, 0x01, 0x03, clamp_ui_brightness(brightness), 0x08, 0x00, 0x00))


def build_turn_off_reports() -> tuple[bytes, ...]:
    return (
        bytes((0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        build_zone_disable_report(),
    )
