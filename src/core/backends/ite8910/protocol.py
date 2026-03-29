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
RAW_SPEED_MAX = 0x0A

REPORT_ID = 0xCC
LED_ID_ROW_STRIDE = 0x20

# Protocol documentation:
# https://chocapikk.com/posts/2026/reverse-engineering-ite8910-keyboard-rgb/
#
# All commands are 6-byte HID feature reports with report ID 0xCC:
# [0xCC, command, data0, data1, data2, data3]
#
# Command reference (from reverse-engineered .NET IL and native DLL):
#   0x00 XX       - Animation mode select (XX = mode ID)
#   0x01 ID R G B - Set single key color
#   0x09 BR SP    - Set brightness (0x00-0x0A) and speed (0x00-0x0A)
#   0x0A 00       - Breathing with random colors
#   0x0A AA R G B - Breathing with custom color
#   0x0B 00       - Flashing with random colors
#   0x0B AA R G B - Flashing with custom color
#   0x15 SL R G B - Wave color slot (SL: 0xA1-0xA8 custom, 0x71-0x78 preset)
#   0x16 SL R G B - Snake color slot (SL: 0xA1-0xA4 custom, 0x71-0x74 preset)
#   0x17 SL R G B - Scan color slot (SL: 0xA1-0xA2)
#   0x18 A1 R G B - Random with custom color


# Animation mode IDs for command [CC, 00, XX]
class AnimationMode(IntEnum):
    SPECTRUM_CYCLE = 0x02
    RAINBOW_WAVE = 0x04
    RANDOM = 0x09
    SCAN = 0x0A
    SNAKE = 0x0B
    CLEAR = 0x0C


# Color slot base for custom colors
COLOR_SLOT_CUSTOM_BASE = 0xA1
COLOR_SLOT_PRESET_BASE = 0x71

# Commands for color effects with random/custom variants
CMD_SET_LED = 0x01
CMD_BRIGHTNESS_SPEED = 0x09
CMD_BREATHING = 0x0A
CMD_FLASHING = 0x0B
CMD_WAVE_COLOR = 0x15
CMD_SNAKE_COLOR = 0x16
CMD_SCAN_COLOR = 0x17
CMD_RANDOM_COLOR = 0x18
CMD_ANIMATION = 0x00

# Wave supports 8 custom color slots
WAVE_MAX_COLORS = 8
# Snake supports 4 custom color slots
SNAKE_MAX_COLORS = 4
# Scan supports 2 custom color slots
SCAN_MAX_COLORS = 2


# LED ID encoding: ((row & 0x07) << 5) | (col & 0x1F)
KNOWN_LED_IDS: tuple[int, ...] = tuple(
    ((row & 0x07) << 5) | (col & 0x1F)
    for row in range(NUM_ROWS)
    for col in range(NUM_COLS)
)


class Ite8910Effect(IntEnum):
    SPECTRUM_CYCLE = 0
    RAINBOW_WAVE = 1
    BREATHING = 2
    BREATHING_COLOR = 3
    FLASHING = 4
    FLASHING_COLOR = 5
    RANDOM = 6
    RANDOM_COLOR = 7
    SCAN = 8
    SNAKE = 9
    FN_HIGHLIGHT = 10
    OFF = 11


CANONICAL_EFFECTS: dict[str, Ite8910Effect] = {
    "spectrum_cycle": Ite8910Effect.SPECTRUM_CYCLE,
    "rainbow_wave": Ite8910Effect.RAINBOW_WAVE,
    "rainbow": Ite8910Effect.RAINBOW_WAVE,
    "breathing": Ite8910Effect.BREATHING,
    "breathing_color": Ite8910Effect.BREATHING_COLOR,
    "flashing": Ite8910Effect.FLASHING,
    "flashing_color": Ite8910Effect.FLASHING_COLOR,
    "random": Ite8910Effect.RANDOM,
    "random_color": Ite8910Effect.RANDOM_COLOR,
    "scan": Ite8910Effect.SCAN,
    "snake": Ite8910Effect.SNAKE,
    "fn_highlight": Ite8910Effect.FN_HIGHLIGHT,
    "off": Ite8910Effect.OFF,
}

_EFFECT_ALIASES: dict[str, Ite8910Effect] = {
    **CANONICAL_EFFECTS,
    "breathe": Ite8910Effect.BREATHING,
    "blink": Ite8910Effect.FLASHING,
    "wave": Ite8910Effect.RAINBOW_WAVE,
}


def clamp_channel(value: int) -> int:
    return max(0, min(0xFF, int(value)))


def clamp_raw_brightness(value: int) -> int:
    return max(0, min(RAW_BRIGHTNESS_MAX, int(value)))


def clamp_raw_speed(value: int) -> int:
    return max(0, min(RAW_SPEED_MAX, int(value)))


def raw_speed_from_effect_speed(value: int) -> int:
    """Map KeyRGB's generic hardware-effect speed arg to the 0..10 ITE 8910 scale.

    The firmware accepts speed values 0x00 (slowest) to 0x0A (fastest).
    The Windows Control Center maps 4 UI levels to: 1->0x02, 2->0x04, 3->0x06, 4->0x0A.
    """

    try:
        speed_value = int(value)
    except Exception:
        return 0

    return clamp_raw_speed(max(0, min(10, speed_value)))


def raw_brightness_from_ui(value: int) -> int:
    """Map KeyRGB's 0..50 UI brightness into the controller's 0..10 scale.

    The Windows Control Center maps 4 UI levels to: 1->0x02, 2->0x04, 3->0x06, 4->0x0A.
    Values above 0x0A cause undefined firmware behavior.
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
    return ((int(row) & 0x07) << 5) | (int(col) & 0x1F)


def iter_matrix_led_ids() -> Iterable[int]:
    for row in range(NUM_ROWS):
        for col in range(NUM_COLS):
            yield led_id_from_row_col(row, col)


def iter_known_led_ids() -> Iterable[int]:
    yield from KNOWN_LED_IDS


# --- Report builders ---
# All reports are 6 bytes: [REPORT_ID, cmd/data0, data1, data2, data3, data4]


def build_brightness_speed_report(brightness_raw: int, speed_raw: int) -> bytes:
    """[CC, 09, brightness, speed, 00, 00]"""
    return bytes((
        REPORT_ID, CMD_BRIGHTNESS_SPEED,
        clamp_raw_brightness(brightness_raw),
        clamp_raw_speed(speed_raw),
        0x00, 0x00,
    ))


def build_animation_mode_report(mode: AnimationMode) -> bytes:
    """[CC, 00, mode, 00, 00, 00]"""
    return bytes((REPORT_ID, CMD_ANIMATION, int(mode), 0x00, 0x00, 0x00))


def build_reset_report() -> bytes:
    """[CC, 00, 0C, 00, 00, 00] - Clear all LEDs, required before per-key updates."""
    return build_animation_mode_report(AnimationMode.CLEAR)


def build_led_color_report(led_id: int, color: tuple[int, int, int]) -> bytes:
    """[CC, 01, led_id, R, G, B]"""
    r, g, b = color
    return bytes((
        REPORT_ID, CMD_SET_LED,
        int(led_id) & 0xFF,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_breathing_random_report() -> bytes:
    """[CC, 0A, 00, 00, 00, 00] - Breathing with random colors."""
    return bytes((REPORT_ID, CMD_BREATHING, 0x00, 0x00, 0x00, 0x00))


def build_breathing_color_report(r: int, g: int, b: int) -> bytes:
    """[CC, 0A, AA, R, G, B] - Breathing with custom color."""
    return bytes((
        REPORT_ID, CMD_BREATHING, 0xAA,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_flashing_random_report() -> bytes:
    """[CC, 0B, 00, 00, 00, 00] - Flashing with random colors."""
    return bytes((REPORT_ID, CMD_FLASHING, 0x00, 0x00, 0x00, 0x00))


def build_flashing_color_report(r: int, g: int, b: int) -> bytes:
    """[CC, 0B, AA, R, G, B] - Flashing with custom color."""
    return bytes((
        REPORT_ID, CMD_FLASHING, 0xAA,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_random_color_report(r: int, g: int, b: int) -> bytes:
    """[CC, 18, A1, R, G, B] - Random with custom color."""
    return bytes((
        REPORT_ID, CMD_RANDOM_COLOR, COLOR_SLOT_CUSTOM_BASE,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_wave_color_slot_report(slot: int, r: int, g: int, b: int) -> bytes:
    """[CC, 15, slot, R, G, B] - Set wave color slot (0-7 -> 0xA1-0xA8)."""
    slot_id = COLOR_SLOT_CUSTOM_BASE + max(0, min(WAVE_MAX_COLORS - 1, int(slot)))
    return bytes((
        REPORT_ID, CMD_WAVE_COLOR, slot_id,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_snake_color_slot_report(slot: int, r: int, g: int, b: int) -> bytes:
    """[CC, 16, slot, R, G, B] - Set snake color slot (0-3 -> 0xA1-0xA4)."""
    slot_id = COLOR_SLOT_CUSTOM_BASE + max(0, min(SNAKE_MAX_COLORS - 1, int(slot)))
    return bytes((
        REPORT_ID, CMD_SNAKE_COLOR, slot_id,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_scan_color_slot_report(slot: int, r: int, g: int, b: int) -> bytes:
    """[CC, 17, slot, R, G, B] - Set scan color slot (0-1 -> 0xA1-0xA2)."""
    slot_id = COLOR_SLOT_CUSTOM_BASE + max(0, min(SCAN_MAX_COLORS - 1, int(slot)))
    return bytes((
        REPORT_ID, CMD_SCAN_COLOR, slot_id,
        clamp_channel(r), clamp_channel(g), clamp_channel(b),
    ))


def build_effect_reports(effect: Ite8910Effect, colors: list[tuple[int, int, int]] | None = None) -> list[bytes]:
    """Build the correct sequence of reports for an effect.

    The Windows Control Center follows this sequence:
    1. Set animation mode
    2. Set color slots if applicable
    3. Set brightness and speed (handled separately)

    For per-key Direct mode:
    1. Clear all LEDs (reset)
    2. Set brightness and speed
    3. Set each key color
    """
    reports: list[bytes] = []
    colors = colors or []

    if effect == Ite8910Effect.SPECTRUM_CYCLE:
        reports.append(build_animation_mode_report(AnimationMode.SPECTRUM_CYCLE))

    elif effect == Ite8910Effect.RAINBOW_WAVE:
        reports.append(build_animation_mode_report(AnimationMode.RAINBOW_WAVE))
        for i, (r, g, b) in enumerate(colors[:WAVE_MAX_COLORS]):
            reports.append(build_wave_color_slot_report(i, r, g, b))

    elif effect == Ite8910Effect.BREATHING:
        reports.append(build_breathing_random_report())

    elif effect == Ite8910Effect.BREATHING_COLOR:
        if colors:
            r, g, b = colors[0]
            reports.append(build_breathing_color_report(r, g, b))
        else:
            reports.append(build_breathing_random_report())

    elif effect == Ite8910Effect.FLASHING:
        reports.append(build_flashing_random_report())

    elif effect == Ite8910Effect.FLASHING_COLOR:
        if colors:
            r, g, b = colors[0]
            reports.append(build_flashing_color_report(r, g, b))
        else:
            reports.append(build_flashing_random_report())

    elif effect == Ite8910Effect.RANDOM:
        reports.append(build_animation_mode_report(AnimationMode.RANDOM))

    elif effect == Ite8910Effect.RANDOM_COLOR:
        reports.append(build_animation_mode_report(AnimationMode.RANDOM))
        if colors:
            r, g, b = colors[0]
            reports.append(build_random_color_report(r, g, b))

    elif effect == Ite8910Effect.SCAN:
        reports.append(build_animation_mode_report(AnimationMode.SCAN))
        for i, (r, g, b) in enumerate(colors[:SCAN_MAX_COLORS]):
            reports.append(build_scan_color_slot_report(i, r, g, b))

    elif effect == Ite8910Effect.SNAKE:
        reports.append(build_animation_mode_report(AnimationMode.SNAKE))
        for i, (r, g, b) in enumerate(colors[:SNAKE_MAX_COLORS]):
            reports.append(build_snake_color_slot_report(i, r, g, b))

    elif effect == Ite8910Effect.FN_HIGHLIGHT:
        reports.append(build_animation_mode_report(AnimationMode.SPECTRUM_CYCLE))

    elif effect == Ite8910Effect.OFF:
        reports.append(build_animation_mode_report(AnimationMode.CLEAR))

    return reports


# Legacy aliases for backward compatibility with existing keyRGB code
build_brightness_speed_report_raw = build_brightness_speed_report


def build_effect_report(effect: Ite8910Effect | int | str) -> bytes:
    """Legacy single-report interface. Returns the first report of the effect sequence."""
    reports = build_effect_reports(normalize_effect(effect))
    return reports[0] if reports else build_reset_report()


@dataclass
class Ite8910ProtocolState:
    """Stateful protocol handler.

    Tracks brightness and speed state as the firmware expects both
    to be sent together in a single command.
    """

    current_brightness_raw: int = 0
    current_speed_raw: int = 0

    def set_brightness_and_speed_raw(self, brightness_raw: int, speed_raw: int) -> bytes:
        self.current_brightness_raw = clamp_raw_brightness(brightness_raw)
        self.current_speed_raw = clamp_raw_speed(speed_raw)
        return build_brightness_speed_report(self.current_brightness_raw, self.current_speed_raw)

    def set_brightness_raw(self, brightness_raw: int) -> bytes:
        return self.set_brightness_and_speed_raw(brightness_raw, self.current_speed_raw)

    def set_speed_raw(self, speed_raw: int) -> bytes:
        return self.set_brightness_and_speed_raw(self.current_brightness_raw, speed_raw)

    def set_effect(self, effect: Ite8910Effect | int | str, colors: list[tuple[int, int, int]] | None = None) -> list[bytes]:
        return build_effect_reports(normalize_effect(effect), colors)

    def reset(self) -> bytes:
        return build_reset_report()

    def set_led_color(self, led_id: int, color: tuple[int, int, int]) -> bytes:
        return build_led_color_report(led_id, color)
