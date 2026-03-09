from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from math import ceil
from typing import Iterable

VENDOR_ID = 0x048D
PRODUCT_ID = 0x8910

NUM_ROWS = 6
NUM_COLS = 20

UI_BRIGHTNESS_MAX = 50
RAW_BRIGHTNESS_MAX = 0x0A
RAW_SPEED_MAX = 0x02

REPORT_ID = 0xCC
REPORT_TRAILER = 0x7F
LED_ID_ROW_STRIDE = 0x20

# LED ranges documented by the public `ite-829x.c` userspace tool.
# These are the ids that tool explicitly describes as valid keyboard LEDs.
LED_ID_RANGES: tuple[tuple[int, int], ...] = (
    (0, 19),
    (32, 43),
    (45, 51),
    (64, 83),
    (96, 108),
    (110, 115),
    (128, 128),
    (130, 147),
    (160, 165),
    (169, 179),
)

KNOWN_LED_IDS: tuple[int, ...] = tuple(
    led_id
    for start, end in LED_ID_RANGES
    for led_id in range(int(start), int(end) + 1)
)


class Ite8910Effect(IntEnum):
    WAVE = 0
    BREATHING = 1
    SCAN = 2
    BLINK = 3
    RANDOM = 4
    RIPPLE = 5
    SNAKE = 6


CANONICAL_EFFECTS: dict[str, Ite8910Effect] = {
    "wave": Ite8910Effect.WAVE,
    "breathing": Ite8910Effect.BREATHING,
    "scan": Ite8910Effect.SCAN,
    "blink": Ite8910Effect.BLINK,
    "random": Ite8910Effect.RANDOM,
    "ripple": Ite8910Effect.RIPPLE,
    "snake": Ite8910Effect.SNAKE,
}

_EFFECT_ALIASES: dict[str, Ite8910Effect] = {
    **CANONICAL_EFFECTS,
    "breathe": Ite8910Effect.BREATHING,
}

_EFFECT_REPORT_FIELDS: dict[Ite8910Effect, tuple[int, int, int]] = {
    Ite8910Effect.WAVE: (0x00, 0x04, 0x7F),
    Ite8910Effect.BREATHING: (0x0A, 0x00, 0x7F),
    Ite8910Effect.SCAN: (0x00, 0x0A, 0x7F),
    Ite8910Effect.BLINK: (0x0B, 0x00, 0x7F),
    Ite8910Effect.RANDOM: (0x00, 0x09, 0x00),
    Ite8910Effect.RIPPLE: (0x07, 0x00, 0x00),
    Ite8910Effect.SNAKE: (0x00, 0x0B, 0x53),
}


def clamp_channel(value: int) -> int:
    return max(0, min(0xFF, int(value)))


def clamp_raw_brightness(value: int) -> int:
    return max(0, min(RAW_BRIGHTNESS_MAX, int(value)))


def clamp_raw_speed(value: int) -> int:
    return max(0, min(RAW_SPEED_MAX, int(value)))


def raw_speed_from_effect_speed(value: int) -> int:
    """Map KeyRGB's generic hardware-effect speed arg to the 0..2 ITE 8910 scale.

    `build_hw_effect_payload()` currently produces a 1..10 speed argument where
    smaller values are faster. The original public C backend exposes 3 steps.
    """

    try:
        speed_value = int(value)
    except Exception:
        return 0

    if speed_value <= 0:
        return 0

    speed_value = max(1, min(10, speed_value))
    if speed_value <= 3:
        return 0
    if speed_value <= 7:
        return 1
    return 2


def raw_brightness_from_ui(value: int) -> int:
    """Map KeyRGB's 0..50 UI brightness into the controller's 0..10 scale.

    This scaling is a KeyRGB adapter layer, not part of the upstream C CLI.
    Non-zero UI values stay non-zero on hardware.
    """

    ui_value = max(0, min(UI_BRIGHTNESS_MAX, int(value)))
    if ui_value == 0:
        return 0
    return clamp_raw_brightness(int(ceil((ui_value * RAW_BRIGHTNESS_MAX) / UI_BRIGHTNESS_MAX)))


def ui_brightness_from_raw(value: int) -> int:
    raw_value = clamp_raw_brightness(value)
    if raw_value == 0:
        return 0
    scaled = int(round((raw_value / RAW_BRIGHTNESS_MAX) * UI_BRIGHTNESS_MAX))
    return max(1, min(UI_BRIGHTNESS_MAX, scaled))


def normalize_effect(effect: Ite8910Effect | int | str) -> Ite8910Effect:
    if isinstance(effect, Ite8910Effect):
        return effect

    if isinstance(effect, str):
        key = effect.strip().lower().replace(" ", "_")
        try:
            return _EFFECT_ALIASES[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported ITE 8910 effect: {effect}") from exc

    try:
        return Ite8910Effect(int(effect))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported ITE 8910 effect: {effect}") from exc


def led_id_from_row_col(row: int, col: int) -> int:
    """Translate a logical matrix coordinate to the controller LED id.

    This follows the `get_led_id(row, col)` macro from the vendored TUXEDO
    `ite_829x` kernel driver for the same controller family.

    Note: this row/column helper is a KeyRGB adapter convenience. The public C
    CLI itself works directly with LED ids.
    """

    return ((int(row) & 0x07) << 5) | (int(col) & 0x1F)


def iter_matrix_led_ids() -> Iterable[int]:
    """Yield the full derived 6x20 matrix id space from the kernel-driver macro."""

    for row in range(NUM_ROWS):
        for col in range(NUM_COLS):
            yield led_id_from_row_col(row, col)


def iter_known_led_ids() -> Iterable[int]:
    """Yield the exact LED ids documented by the public upstream C backend."""

    yield from KNOWN_LED_IDS


def build_brightness_speed_report_raw(brightness_raw: int, speed_raw: int) -> bytes:
    return bytes(
        (
            REPORT_ID,
            0x09,
            clamp_raw_brightness(brightness_raw),
            clamp_raw_speed(speed_raw),
            0x00,
            0x00,
            REPORT_TRAILER,
        )
    )


def build_effect_report(effect: Ite8910Effect | int | str) -> bytes:
    effect1, effect2, last = _EFFECT_REPORT_FIELDS[normalize_effect(effect)]
    return bytes((REPORT_ID, effect1, effect2, 0x00, 0x00, 0x00, last))


def build_reset_report() -> bytes:
    return bytes((REPORT_ID, 0x00, 0x0C, 0x00, 0x00, 0x00, REPORT_TRAILER))


def build_led_color_report(led_id: int, color: tuple[int, int, int]) -> bytes:
    red, green, blue = color
    return bytes(
        (
            REPORT_ID,
            0x01,
            int(led_id) & 0xFF,
            clamp_channel(red),
            clamp_channel(green),
            clamp_channel(blue),
            REPORT_TRAILER,
        )
    )


@dataclass
class Ite8910ProtocolState:
    """Stateful translation of the upstream C command helpers.

    The original userspace tool preserves the last brightness and speed values,
    and reuses that state when only one side of the pair changes.
    """

    current_brightness_raw: int = 0
    current_speed_raw: int = 0

    def set_brightness_and_speed_raw(self, brightness_raw: int, speed_raw: int) -> bytes:
        self.current_brightness_raw = clamp_raw_brightness(brightness_raw)
        self.current_speed_raw = clamp_raw_speed(speed_raw)
        return build_brightness_speed_report_raw(self.current_brightness_raw, self.current_speed_raw)

    def set_brightness_raw(self, brightness_raw: int) -> bytes:
        return self.set_brightness_and_speed_raw(brightness_raw, self.current_speed_raw)

    def set_speed_raw(self, speed_raw: int) -> bytes:
        return self.set_brightness_and_speed_raw(self.current_brightness_raw, speed_raw)

    def set_effect(self, effect: Ite8910Effect | int | str) -> bytes:
        return build_effect_report(effect)

    def reset(self) -> bytes:
        return build_reset_report()

    def set_led_color(self, led_id: int, color: tuple[int, int, int]) -> bytes:
        return build_led_color_report(led_id, color)