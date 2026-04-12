from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import SupportsIndex, SupportsInt, cast

HIDRAW_PATH_ENV = "KEYRGB_ITE8295_ZONES_HIDRAW_PATH"

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0xC963,)

USAGE_PAGE = 0xFF89
USAGE = 0x00CC

PACKET_SIZE = 33
NUM_ZONES = 4
ZONE_NAMES: tuple[str, ...] = ("Left side", "Left center", "Right center", "Right side")

HEADER_0 = 0xCC
HEADER_1 = 0x16

EFFECT_STATIC = 0x01
EFFECT_BREATHING = 0x03
EFFECT_WAVE = 0x04
EFFECT_SMOOTH = 0x06

UI_BRIGHTNESS_MAX = 50
RAW_BRIGHTNESS_LOW = 0x01
RAW_BRIGHTNESS_HIGH = 0x02

UI_SPEED_MAX = 10
RAW_SPEED_MIN = 0x01
RAW_SPEED_MAX = 0x04

Color = tuple[int, int, int]
IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def clamp_channel(value: object) -> int:
    return max(0, min(255, _coerce_int(value)))


def clamp_ui_brightness(value: object) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, _coerce_int(value)))


def raw_brightness_from_ui(value: object) -> int:
    level = clamp_ui_brightness(value)
    if level <= 0:
        return 0
    midpoint = UI_BRIGHTNESS_MAX // 2
    return RAW_BRIGHTNESS_LOW if level <= midpoint else RAW_BRIGHTNESS_HIGH


def raw_speed_from_ui(value: object) -> int:
    level = max(0, min(UI_SPEED_MAX, _coerce_int(value)))
    scaled = round((level / UI_SPEED_MAX) * (RAW_SPEED_MAX - RAW_SPEED_MIN))
    return max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, RAW_SPEED_MIN + scaled))


def normalize_effect_name(effect_name: object) -> str:
    return str(effect_name or "").strip().lower().replace(" ", "_")


def _coerce_rgb(color: object) -> Color:
    try:
        red, green, blue = cast(Iterable[object], color)
    except (TypeError, ValueError) as exc:
        raise ValueError("color must be an RGB 3-tuple") from exc
    return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))


def uniform_zone_colors(color: object) -> tuple[Color, ...]:
    rgb = _coerce_rgb(color)
    return tuple(rgb for _ in range(NUM_ZONES))


def normalize_zone_colors(colors: object, *, fallback: Color = (255, 255, 255)) -> tuple[Color, ...]:
    if colors is None:
        return uniform_zone_colors(fallback)
    if isinstance(colors, tuple) and len(colors) == 3:
        return uniform_zone_colors(colors)
    if not isinstance(colors, (list, tuple)):
        raise ValueError("zone colors must be a 4-item sequence or a single RGB tuple")
    if len(colors) != NUM_ZONES:
        raise ValueError(f"zone colors must contain exactly {NUM_ZONES} entries")
    return tuple(_coerce_rgb(color) for color in colors)


def wave_direction_flags(direction: object) -> tuple[int, int]:
    normalized = str(direction or "").strip().lower().replace("-", "_")
    if normalized in {"left", "rtl", "right_to_left", "wave_rtl"}:
        return (0, 1)
    return (1, 0)


@dataclass(frozen=True)
class LightingState:
    effect: int
    speed: int
    brightness: int
    zone_colors: tuple[Color, ...]
    wave_ltr: int = 0
    wave_rtl: int = 0


def build_report(state: LightingState) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0] = HEADER_0
    packet[1] = HEADER_1
    packet[2] = int(state.effect) & 0xFF
    packet[3] = int(state.speed) & 0xFF
    packet[4] = int(state.brightness) & 0xFF

    offset = 5
    for red, green, blue in normalize_zone_colors(state.zone_colors):
        packet[offset] = red
        packet[offset + 1] = green
        packet[offset + 2] = blue
        offset += 3

    packet[17] = 0x00
    packet[18] = int(state.wave_ltr) & 0xFF
    packet[19] = int(state.wave_rtl) & 0xFF
    return bytes(packet)


def build_static_report(zone_colors: object, *, brightness: int) -> bytes:
    return build_report(
        LightingState(
            effect=EFFECT_STATIC,
            speed=RAW_SPEED_MIN,
            brightness=max(RAW_BRIGHTNESS_LOW, int(brightness)),
            zone_colors=normalize_zone_colors(zone_colors, fallback=(0, 0, 0)),
        )
    )


def build_breathing_report(zone_colors: object, *, brightness: int, speed: int) -> bytes:
    return build_report(
        LightingState(
            effect=EFFECT_BREATHING,
            speed=max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(speed))),
            brightness=max(RAW_BRIGHTNESS_LOW, int(brightness)),
            zone_colors=normalize_zone_colors(zone_colors),
        )
    )


def build_wave_report(
    zone_colors: object | None = None, *, brightness: int, speed: int, direction: object = None
) -> bytes:
    wave_ltr, wave_rtl = wave_direction_flags(direction)
    return build_report(
        LightingState(
            effect=EFFECT_WAVE,
            speed=max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(speed))),
            brightness=max(RAW_BRIGHTNESS_LOW, int(brightness)),
            zone_colors=normalize_zone_colors(zone_colors),
            wave_ltr=wave_ltr,
            wave_rtl=wave_rtl,
        )
    )


def build_smooth_report(zone_colors: object | None = None, *, brightness: int, speed: int) -> bytes:
    return build_report(
        LightingState(
            effect=EFFECT_SMOOTH,
            speed=max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(speed))),
            brightness=max(RAW_BRIGHTNESS_LOW, int(brightness)),
            zone_colors=normalize_zone_colors(zone_colors),
        )
    )


def build_turn_off_report() -> bytes:
    return build_static_report(((0, 0, 0),) * NUM_ZONES, brightness=RAW_BRIGHTNESS_LOW)
