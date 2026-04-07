from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

HIDRAW_PATH_ENV = "KEYRGB_ITE8258_HIDRAW_PATH"

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0xC195,)

USAGE_PAGE = 0xFF89
USAGE = 0x07

PACKET_SIZE = 960
REPORT_ID = 0x07

SAVE_PROFILE = 0xCB
SET_BRIGHTNESS = 0xCE

DEFAULT_PROFILE_ID = 0x01

NUM_ROWS = 4
NUM_COLS = 6
NUM_ZONES = NUM_ROWS * NUM_COLS
LED_IDS: tuple[int, ...] = tuple(range(0x01, 0x19))

UI_BRIGHTNESS_MAX = 50
RAW_BRIGHTNESS_MAX = 9

UI_SPEED_MAX = 10
RAW_SPEED_MIN = 1
RAW_SPEED_MAX = 3

MODE_SCREW_RAINBOW = 0x01
MODE_RAINBOW_WAVE = 0x02
MODE_COLOR_CHANGE = 0x03
MODE_COLOR_PULSE = 0x04
MODE_COLOR_WAVE = 0x05
MODE_SMOOTH = 0x06
MODE_STATIC = 0x0B

COLOR_MODE_NONE = 0x00
COLOR_MODE_RANDOM = 0x01
COLOR_MODE_CUSTOM = 0x02

SPIN_RIGHT = 0x01
SPIN_LEFT = 0x02

DIRECTION_UP = 0x01
DIRECTION_DOWN = 0x02
DIRECTION_LEFT = 0x03
DIRECTION_RIGHT = 0x04

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Ite8258Group:
    mode: int
    speed: int
    spin: int
    direction: int
    color_mode: int
    colors: tuple[Color, ...]
    leds: tuple[int, ...]


_EFFECT_MODE_BY_NAME: dict[str, int] = {
    "rainbow": MODE_SCREW_RAINBOW,
    "screw_rainbow": MODE_SCREW_RAINBOW,
    "rainbow_wave": MODE_RAINBOW_WAVE,
    "color_change": MODE_COLOR_CHANGE,
    "color_pulse": MODE_COLOR_PULSE,
    "color_wave": MODE_COLOR_WAVE,
    "smooth": MODE_SMOOTH,
    "static": MODE_STATIC,
}


def clamp_channel(value: object) -> int:
    return max(0, min(255, int(value)))


def clamp_ui_brightness(value: object) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, int(value)))


def raw_brightness_from_ui(value: object) -> int:
    level = clamp_ui_brightness(value)
    if level <= 0:
        return 0
    return max(1, min(RAW_BRIGHTNESS_MAX, round((level / UI_BRIGHTNESS_MAX) * RAW_BRIGHTNESS_MAX)))


def raw_speed_from_ui(value: object) -> int:
    ui_speed = max(0, min(UI_SPEED_MAX, int(value)))
    scaled = round((ui_speed / UI_SPEED_MAX) * (RAW_SPEED_MAX - RAW_SPEED_MIN))
    return max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, RAW_SPEED_MIN + scaled))


def led_id_from_row_col(row: int, col: int) -> int:
    row_i = int(row)
    col_i = int(col)
    if row_i < 0 or row_i >= NUM_ROWS:
        raise ValueError(f"row must be between 0 and {NUM_ROWS - 1} inclusive")
    if col_i < 0 or col_i >= NUM_COLS:
        raise ValueError(f"col must be between 0 and {NUM_COLS - 1} inclusive")
    return (row_i * NUM_COLS) + col_i + 1


def iter_known_led_ids() -> tuple[int, ...]:
    return LED_IDS


def _coerce_rgb(color: object) -> Color:
    try:
        red, green, blue = color  # type: ignore[misc]
    except (TypeError, ValueError) as exc:
        raise ValueError("color must be an RGB 3-tuple") from exc
    return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))


def _normalize_effect_name(effect_name: object) -> str:
    return str(effect_name or "").strip().lower().replace(" ", "_")


def _direction_code(direction: object, *, default: int = DIRECTION_RIGHT) -> int:
    normalized = str(direction or "").strip().lower().replace("-", "_")
    if normalized in {"up", "1", str(DIRECTION_UP)}:
        return DIRECTION_UP
    if normalized in {"down", "2", str(DIRECTION_DOWN)}:
        return DIRECTION_DOWN
    if normalized in {"left", "3", str(DIRECTION_LEFT)}:
        return DIRECTION_LEFT
    if normalized in {"right", "4", str(DIRECTION_RIGHT), ""}:
        return DIRECTION_RIGHT
    return int(default)


def _spin_code(direction: object) -> int:
    normalized = str(direction or "").strip().lower().replace("-", "_")
    if normalized in {"left", str(SPIN_LEFT)}:
        return SPIN_LEFT
    return SPIN_RIGHT


def _packet(command: int, payload_length: int) -> bytearray:
    packet = bytearray(PACKET_SIZE)
    packet[0] = REPORT_ID
    packet[1] = int(command) & 0xFF
    packet[2] = int(payload_length) & 0xFF
    packet[3] = (int(payload_length) >> 8) & 0xFF
    return packet


def build_set_brightness_report(brightness_raw: int) -> bytes:
    packet = _packet(SET_BRIGHTNESS, 1)
    packet[4] = max(0, min(RAW_BRIGHTNESS_MAX, int(brightness_raw)))
    return bytes(packet)


def build_turn_off_report(*, profile_id: int = DEFAULT_PROFILE_ID) -> bytes:
    packet = _packet(SAVE_PROFILE, 3)
    packet[4] = int(profile_id) & 0xFF
    packet[5] = 0x01
    packet[6] = 0x01
    return bytes(packet)


def _encode_group(group_index: int, group: Ite8258Group) -> bytes:
    payload = bytearray()
    payload.append((int(group_index) + 1) & 0xFF)
    payload.append(0x06)
    payload.extend((0x01, int(group.mode) & 0xFF))
    payload.extend((0x02, int(group.speed) & 0xFF))
    payload.extend((0x03, int(group.spin) & 0xFF))
    payload.extend((0x04, int(group.direction) & 0xFF))
    payload.extend((0x05, int(group.color_mode) & 0xFF))
    payload.extend((0x06, 0x00))
    payload.append(len(group.colors) & 0xFF)
    for color in group.colors:
        payload.extend(_coerce_rgb(color))
    payload.append(len(group.leds) & 0xFF)
    for led_id in group.leds:
        payload.append(int(led_id) & 0xFF)
        payload.append((int(led_id) >> 8) & 0xFF)
    return bytes(payload)


def build_save_profile_reports(profile_id: int, groups: Sequence[Ite8258Group]) -> tuple[bytes, ...]:
    if not groups:
        return ()

    reports: list[bytes] = []
    group_index = 0
    while group_index < len(groups):
        packet = _packet(SAVE_PROFILE, 0)
        offset = 4
        packet[offset] = int(profile_id) & 0xFF
        packet[offset + 1] = 0x01
        packet[offset + 2] = 0x01
        offset += 3

        wrote_group = False
        while group_index < len(groups):
            encoded = _encode_group(group_index, groups[group_index])
            if offset + len(encoded) > PACKET_SIZE:
                break
            packet[offset : offset + len(encoded)] = encoded
            offset += len(encoded)
            wrote_group = True
            group_index += 1

        if not wrote_group:
            raise ValueError("group payload exceeds ITE 8258 packet size")

        payload_length = offset - 4
        packet[2] = payload_length & 0xFF
        packet[3] = (payload_length >> 8) & 0xFF
        reports.append(bytes(packet))

    return tuple(reports)


def build_uniform_static_groups(color: object) -> tuple[Ite8258Group, ...]:
    rgb = _coerce_rgb(color)
    return (
        Ite8258Group(
            mode=MODE_STATIC,
            speed=raw_speed_from_ui(UI_SPEED_MAX // 2),
            spin=0x00,
            direction=0x00,
            color_mode=COLOR_MODE_CUSTOM,
            colors=(rgb,),
            leds=LED_IDS,
        ),
    )


def build_static_groups(zone_colors: Sequence[object]) -> tuple[Ite8258Group, ...]:
    if len(zone_colors) != NUM_ZONES:
        raise ValueError(f"zone_colors must contain exactly {NUM_ZONES} entries")

    grouped: OrderedDict[Color, list[int]] = OrderedDict()
    for led_id, color in zip(LED_IDS, zone_colors):
        rgb = _coerce_rgb(color)
        grouped.setdefault(rgb, []).append(int(led_id))

    groups: list[Ite8258Group] = []
    for color, leds in grouped.items():
        groups.append(
            Ite8258Group(
                mode=MODE_STATIC,
                speed=raw_speed_from_ui(UI_SPEED_MAX // 2),
                spin=0x00,
                direction=0x00,
                color_mode=COLOR_MODE_CUSTOM,
                colors=(color,),
                leds=tuple(leds),
            )
        )
    return tuple(groups)


def build_effect_groups(
    effect_name: object,
    *,
    speed: int,
    color: object | None = None,
    direction: object | None = None,
) -> tuple[Ite8258Group, ...]:
    normalized = _normalize_effect_name(effect_name)
    mode = _EFFECT_MODE_BY_NAME.get(normalized)
    if mode is None or mode == MODE_STATIC:
        raise ValueError(f"unsupported ITE 8258 effect: {effect_name}")

    spin = 0x00
    direction_code = 0x00
    color_mode = COLOR_MODE_NONE
    colors: tuple[Color, ...] = ()

    if normalized in {"rainbow", "screw_rainbow"}:
        spin = _spin_code(direction)
    elif normalized in {"rainbow_wave", "color_wave"}:
        direction_code = _direction_code(direction)

    if normalized in {"color_change", "color_pulse", "color_wave", "smooth"}:
        if color is None:
            color_mode = COLOR_MODE_RANDOM
        else:
            color_mode = COLOR_MODE_CUSTOM
            colors = (_coerce_rgb(color),)

    return (
        Ite8258Group(
            mode=mode,
            speed=max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(speed))),
            spin=spin,
            direction=direction_code,
            color_mode=color_mode,
            colors=colors,
            leds=LED_IDS,
        ),
    )


def build_static_zone_map(color_map: Mapping[int, object]) -> tuple[Color, ...]:
    zone_colors: list[Color] = [(0, 0, 0) for _ in range(NUM_ZONES)]
    for led_id, color in color_map.items():
        led_index = int(led_id) - 1
        if led_index < 0 or led_index >= NUM_ZONES:
            raise ValueError(f"LED id must be between 1 and {NUM_ZONES} inclusive")
        zone_colors[led_index] = _coerce_rgb(color)
    return tuple(zone_colors)