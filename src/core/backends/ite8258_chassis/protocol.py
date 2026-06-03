from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import SupportsIndex, SupportsInt, cast

HIDRAW_PATH_ENV = "KEYRGB_ITE8258_CHASSIS_HIDRAW_PATH"

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0xC197,)

USAGE_PAGE = 0xFF89
USAGE = 0x07

PACKET_SIZE = 960
REPORT_ID = 0x07

DIRECT_MODE = 0xA1
SWITCH_PROFILE = 0xC8
GET_ACTIVE_PROFILE = 0xCA
SAVE_PROFILE = 0xCB
GET_PROFILE = 0xCC
GET_BRIGHTNESS = 0xCD
SET_BRIGHTNESS = 0xCE
SET_DIRECT_MODE = 0xD0
GET_DIRECT_MODE_PROFILE = 0xD1

COMMAND_FAMILY: tuple[int, ...] = (
    DIRECT_MODE,
    SWITCH_PROFILE,
    GET_ACTIVE_PROFILE,
    SAVE_PROFILE,
    GET_PROFILE,
    GET_BRIGHTNESS,
    SET_BRIGHTNESS,
    SET_DIRECT_MODE,
    GET_DIRECT_MODE_PROFILE,
)

# Dormant protocol operations — not yet wired into the device facade
# (discovered in the independent 83F5 working implementation)
GET_KEY_COUNT = 0xC4
GET_KEY_PAGE = 0xC5
RESET_PROFILE = 0xC9
GET_LOGO_STATUS = 0xA5
SET_LOGO_STATUS = 0xA6

DEFAULT_PROFILE_ID = 0x01

NUM_ROWS = 7
NUM_COLS = 20

KEYBOARD_MATRIX_MAP: tuple[int | None, ...] = (
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    None,
    30,
    31,
    32,
    33,
    None,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    None,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    None,
    51,
    52,
    53,
    54,
    None,
    55,
    56,
    None,
    57,
    58,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    None,
    66,
    67,
    None,
    68,
    69,
    70,
    71,
    72,
    None,
    73,
    74,
    75,
    None,
    76,
    77,
    78,
    79,
    80,
    81,
    82,
    None,
    83,
    None,
    84,
    85,
    86,
    None,
    87,
    88,
    89,
    90,
    91,
    None,
    None,
    None,
    None,
    None,
    92,
    93,
    None,
    94,
    None,
    None,
    95,
    None,
    96,
    97,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    98,
    99,
    None,
    100,
    None,
    None,
    None,
    None,
)

KEYBOARD_LED_IDS: tuple[int, ...] = (
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x08,
    0x09,
    0x0A,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x14,
    0x16,
    0x17,
    0x18,
    0x19,
    0x1A,
    0x1B,
    0x1C,
    0x1D,
    0x1E,
    0x1F,
    0x20,
    0x21,
    0x22,
    0x38,
    0x26,
    0x27,
    0x28,
    0x29,
    0x40,
    0x42,
    0x43,
    0x44,
    0x45,
    0x46,
    0x47,
    0x48,
    0x49,
    0x4A,
    0x4B,
    0x4C,
    0x4D,
    0x4E,
    0x4F,
    0x50,
    0x51,
    0x55,
    0x6D,
    0x6E,
    0x58,
    0x59,
    0x5A,
    0x71,
    0x72,
    0x5B,
    0x5C,
    0x5D,
    0x5F,
    0x77,
    0x79,
    0x7B,
    0x7C,
    0x68,
    0x6A,
    0x82,
    0x83,
    0x6F,
    0x70,
    0x87,
    0x88,
    0x73,
    0x74,
    0x75,
    0x76,
    0x8D,
    0x8E,
    0x90,
    0x92,
    0x7F,
    0x80,
    0x96,
    0x97,
    0x98,
    0x9A,
    0x9B,
    0x9D,
    0xA3,
    0xA5,
    0xA7,
    0x9C,
    0x9F,
    0xA1,
)

LED_IDS = KEYBOARD_LED_IDS
NUM_KEYS = len(KEYBOARD_LED_IDS)

KEYBOARD_NUM_ROWS = NUM_ROWS
KEYBOARD_NUM_COLS = NUM_COLS

LOGO_LED_IDS: tuple[int, ...] = (0x05DD,)
VENT_LED_IDS: tuple[int, ...] = (
    0x03E9,
    0x03EA,
    0x03EB,
    0x03EC,
    0x03ED,
    0x03EE,
    0x03EF,
    0x03F0,
    0x03F1,
    0x03F2,
    0x03F3,
    0x03F4,
    0x03F5,
    0x03F6,
    0x03F7,
    0x03F8,
    0x03F9,
    0x03FA,
)
NEON_LED_IDS: tuple[int, ...] = (
    0x01F5,
    0x01F6,
    0x01F7,
    0x01F8,
    0x01F9,
    0x01FA,
    0x01FB,
    0x01FC,
    0x01FD,
    0x01FE,
)

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
MODE_RAIN = 0x07
MODE_RIPPLE = 0x08
MODE_AUDIO_BOUNCE = 0x09
MODE_AUDIO_RIPPLE = 0x0A
MODE_STATIC = 0x0B
MODE_TYPE = 0x0C
MODE_DIRECT = 0x0D

COLOR_MODE_NONE = 0x00
COLOR_MODE_RANDOM = 0x01
COLOR_MODE_CUSTOM = 0x02

SPIN_RIGHT = 0x01
SPIN_LEFT = 0x02

DIRECTION_UP = 0x01
DIRECTION_DOWN = 0x02
DIRECTION_LEFT = 0x04
DIRECTION_RIGHT = 0x03

Color = tuple[int, int, int]
IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


@dataclass(frozen=True)
class Ite8258ChassisGroup:
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
    "rain": MODE_RAIN,
    "ripple": MODE_RIPPLE,
    "audio_bounce": MODE_AUDIO_BOUNCE,
    "audio_ripple": MODE_AUDIO_RIPPLE,
    "type": MODE_TYPE,
}

_LED_ID_TO_INDEX: dict[int, int] = {led_id: index for index, led_id in enumerate(KEYBOARD_LED_IDS)}


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
    return max(1, min(RAW_BRIGHTNESS_MAX, round((level / UI_BRIGHTNESS_MAX) * RAW_BRIGHTNESS_MAX)))


def raw_speed_from_ui(value: object) -> int:
    ui_speed = max(0, min(UI_SPEED_MAX, _coerce_int(value)))
    scaled = round((ui_speed / UI_SPEED_MAX) * (RAW_SPEED_MAX - RAW_SPEED_MIN))
    return max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, RAW_SPEED_MIN + scaled))


def led_id_from_row_col(row: int, col: int) -> int:
    row_i = int(row)
    col_i = int(col)
    if row_i < 0 or row_i >= NUM_ROWS:
        raise ValueError(f"row must be between 0 and {NUM_ROWS - 1} inclusive")
    if col_i < 0 or col_i >= NUM_COLS:
        raise ValueError(f"col must be between 0 and {NUM_COLS - 1} inclusive")

    mapped_index = KEYBOARD_MATRIX_MAP[(row_i * NUM_COLS) + col_i]
    if mapped_index is None:
        raise ValueError(f"row={row_i} col={col_i} does not map to a keyboard LED")
    return KEYBOARD_LED_IDS[mapped_index]


def iter_known_led_ids() -> tuple[int, ...]:
    return KEYBOARD_LED_IDS


def _coerce_rgb(color: object) -> Color:
    try:
        red, green, blue = cast(Iterable[object], color)
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
    # Fixed report size in header, matching the proven 83F5 implementation
    packet[2] = PACKET_SIZE & 0xFF
    packet[3] = (PACKET_SIZE >> 8) & 0xFF
    return packet


def build_switch_profile_report(profile_id: int = DEFAULT_PROFILE_ID) -> bytes:
    packet = _packet(SWITCH_PROFILE, 1)
    packet[4] = int(profile_id) & 0xFF
    return bytes(packet)


def build_get_active_profile_report() -> bytes:
    return bytes(_packet(GET_ACTIVE_PROFILE, 1))


def build_get_brightness_report() -> bytes:
    return bytes(_packet(GET_BRIGHTNESS, 1))


def build_get_profile_report(profile_id: int = DEFAULT_PROFILE_ID) -> bytes:
    packet = _packet(GET_PROFILE, PACKET_SIZE - 4)
    packet[4] = int(profile_id) & 0xFF
    return bytes(packet)


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


def build_set_direct_mode_report(*, enabled: bool, profile_id: int = DEFAULT_PROFILE_ID) -> bytes:
    packet = _packet(SET_DIRECT_MODE, 2)
    packet[4] = 0x01 if enabled else 0x02
    packet[5] = int(profile_id) & 0xFF
    return bytes(packet)


def build_direct_color_report(led_colors: Mapping[int, object] | Sequence[tuple[int, object]]) -> bytes:
    items = list(led_colors.items()) if isinstance(led_colors, Mapping) else list(led_colors)
    if not items:
        raise ValueError("led_colors must not be empty")

    packet = _packet(DIRECT_MODE, len(items) * 5)
    offset = 4
    for led_id, color in items:
        hardware_led_id = int(led_id) & 0xFFFF
        rgb = _coerce_rgb(color)
        if offset + 5 > PACKET_SIZE:
            raise ValueError("direct LED payload exceeds Lenovo Gen10 packet size")
        packet[offset] = hardware_led_id & 0xFF
        packet[offset + 1] = (hardware_led_id >> 8) & 0xFF
        packet[offset + 2 : offset + 5] = bytes(rgb)
        offset += 5
    return bytes(packet)


def _encode_group(group_index: int, group: Ite8258ChassisGroup) -> bytes:
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


def build_save_profile_reports(profile_id: int, groups: Sequence[Ite8258ChassisGroup]) -> tuple[bytes, ...]:
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
            raise ValueError("group payload exceeds Lenovo Gen10 packet size")

        reports.append(bytes(packet))

    return tuple(reports)


def build_uniform_static_groups(color: object) -> tuple[Ite8258ChassisGroup, ...]:
    rgb = _coerce_rgb(color)
    return (
        Ite8258ChassisGroup(
            mode=MODE_STATIC,
            speed=raw_speed_from_ui(UI_SPEED_MAX // 2),
            spin=0x00,
            direction=0x00,
            color_mode=COLOR_MODE_CUSTOM,
            colors=(rgb,),
            leds=KEYBOARD_LED_IDS,
        ),
    )


def build_static_groups(key_colors: Sequence[object]) -> tuple[Ite8258ChassisGroup, ...]:
    if len(key_colors) != NUM_KEYS:
        raise ValueError(f"key_colors must contain exactly {NUM_KEYS} entries")

    grouped: OrderedDict[Color, list[int]] = OrderedDict()
    for led_id, color in zip(KEYBOARD_LED_IDS, key_colors):
        rgb = _coerce_rgb(color)
        grouped.setdefault(rgb, []).append(int(led_id))

    groups: list[Ite8258ChassisGroup] = []
    for color, leds in grouped.items():
        groups.append(
            Ite8258ChassisGroup(
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
) -> tuple[Ite8258ChassisGroup, ...]:
    normalized = _normalize_effect_name(effect_name)
    mode = _EFFECT_MODE_BY_NAME.get(normalized)
    if mode is None:
        raise ValueError(f"unsupported Lenovo Gen10 effect: {effect_name}")

    spin = 0x00
    direction_code = 0x00
    color_mode = COLOR_MODE_NONE
    colors: tuple[Color, ...] = ()

    if normalized in {"rainbow", "screw_rainbow"}:
        spin = _spin_code(direction)
    elif normalized in {"rainbow_wave", "color_wave"}:
        direction_code = _direction_code(direction)

    if normalized in {"color_change", "color_pulse", "color_wave", "smooth", "rain", "ripple", "type"}:
        if color is None:
            color_mode = COLOR_MODE_RANDOM
        else:
            color_mode = COLOR_MODE_CUSTOM
            colors = (_coerce_rgb(color),)

    return (
        Ite8258ChassisGroup(
            mode=mode,
            speed=max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(speed))),
            spin=spin,
            direction=direction_code,
            color_mode=color_mode,
            colors=colors,
            leds=KEYBOARD_LED_IDS,
        ),
    )


def build_static_led_map(color_map: Mapping[int, object]) -> tuple[Color, ...]:
    key_colors: list[Color] = [(0, 0, 0) for _ in range(NUM_KEYS)]
    for led_id, color in color_map.items():
        hardware_led_id = int(led_id) & 0xFFFF
        try:
            led_index = _LED_ID_TO_INDEX[hardware_led_id]
        except KeyError as exc:
            raise ValueError(f"unknown Lenovo Gen10 keyboard LED id: 0x{hardware_led_id:04x}") from exc
        key_colors[led_index] = _coerce_rgb(color)
    return tuple(key_colors)
