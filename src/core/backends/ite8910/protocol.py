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
#   [0xCC, command, data0, data1, data2, data3]
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

Color = tuple[int, int, int]


class AnimationMode(IntEnum):
    """Firmware animation mode IDs for command [CC, 00, XX]."""
    SPECTRUM_CYCLE = 0x02
    RAINBOW_WAVE = 0x04
    RANDOM = 0x09
    SCAN = 0x0A
    SNAKE = 0x0B
    CLEAR = 0x0C


class Cmd(IntEnum):
    """HID report command bytes."""
    ANIMATION = 0x00
    SET_LED = 0x01
    BRIGHTNESS_SPEED = 0x09
    BREATHING = 0x0A
    FLASHING = 0x0B
    WAVE_COLOR = 0x15
    SNAKE_COLOR = 0x16
    SCAN_COLOR = 0x17
    RANDOM_COLOR = 0x18


COLOR_CUSTOM = 0xAA
COLOR_SLOT_BASE = 0xA1

SLOT_LIMITS: dict[Cmd, int] = {
    Cmd.WAVE_COLOR: 8,
    Cmd.SNAKE_COLOR: 4,
    Cmd.SCAN_COLOR: 2,
    Cmd.RANDOM_COLOR: 1,
}


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


_EFFECT_NAMES: dict[str, Ite8910Effect] = {
    "spectrum_cycle": Ite8910Effect.SPECTRUM_CYCLE,
    "rainbow_wave": Ite8910Effect.RAINBOW_WAVE,
    "rainbow": Ite8910Effect.RAINBOW_WAVE,
    "wave": Ite8910Effect.RAINBOW_WAVE,
    "breathing": Ite8910Effect.BREATHING,
    "breathing_color": Ite8910Effect.BREATHING_COLOR,
    "breathe": Ite8910Effect.BREATHING,
    "flashing": Ite8910Effect.FLASHING,
    "flashing_color": Ite8910Effect.FLASHING_COLOR,
    "blink": Ite8910Effect.FLASHING,
    "random": Ite8910Effect.RANDOM,
    "random_color": Ite8910Effect.RANDOM_COLOR,
    "scan": Ite8910Effect.SCAN,
    "snake": Ite8910Effect.SNAKE,
    "fn_highlight": Ite8910Effect.FN_HIGHLIGHT,
    "off": Ite8910Effect.OFF,
}

CANONICAL_EFFECTS = {k: v for k, v in _EFFECT_NAMES.items() if k == v.name.lower()}

KNOWN_LED_IDS: tuple[int, ...] = tuple(
    ((row & 0x07) << 5) | (col & 0x1F)
    for row in range(NUM_ROWS)
    for col in range(NUM_COLS)
)


# --- Helpers ---

def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    return _clamp(r, 0, 0xFF), _clamp(g, 0, 0xFF), _clamp(b, 0, 0xFF)


def _report(*data: int) -> bytes:
    return bytes((REPORT_ID, *data))


clamp_channel = lambda v: _clamp(v, 0, 0xFF)
clamp_raw_brightness = lambda v: _clamp(v, 0, RAW_BRIGHTNESS_MAX)
clamp_raw_speed = lambda v: _clamp(v, 0, RAW_SPEED_MAX)


def raw_speed_from_effect_speed(value: int) -> int:
    """Map KeyRGB's speed arg to the firmware's 0x00-0x0A scale.

    The firmware accepts 0x00 (slowest) to 0x0A (fastest).
    The Windows Control Center maps: 1->0x02, 2->0x04, 3->0x06, 4->0x0A.
    """
    try:
        return clamp_raw_speed(int(value))
    except (TypeError, ValueError):
        return 0


def raw_brightness_from_ui(value: int) -> int:
    """Map KeyRGB's 0..50 UI brightness to the firmware's 0..10 scale.

    Values above 0x0A cause undefined firmware behavior.
    """
    ui = _clamp(value, 0, UI_BRIGHTNESS_MAX)
    return 0 if ui == 0 else clamp_raw_brightness(int(ceil(ui * RAW_BRIGHTNESS_MAX / UI_BRIGHTNESS_MAX)))


def ui_brightness_from_raw(value: int) -> int:
    raw = clamp_raw_brightness(value)
    return 0 if raw == 0 else _clamp(round(raw / RAW_BRIGHTNESS_MAX * UI_BRIGHTNESS_MAX), 1, UI_BRIGHTNESS_MAX)


def normalize_effect(effect: Ite8910Effect | int | str) -> Ite8910Effect:
    if isinstance(effect, Ite8910Effect):
        return effect
    if isinstance(effect, str):
        key = effect.strip().lower().replace(" ", "_")
        if key in _EFFECT_NAMES:
            return _EFFECT_NAMES[key]
        raise ValueError(f"Unsupported ITE 8910 effect: {effect}")
    return Ite8910Effect(int(effect))


def led_id_from_row_col(row: int, col: int) -> int:
    return ((int(row) & 0x07) << 5) | (int(col) & 0x1F)


def iter_matrix_led_ids() -> Iterable[int]:
    for row in range(NUM_ROWS):
        for col in range(NUM_COLS):
            yield led_id_from_row_col(row, col)


def iter_known_led_ids() -> Iterable[int]:
    yield from KNOWN_LED_IDS


# --- Report builders ---

def build_brightness_speed_report(brightness: int, speed: int) -> bytes:
    return _report(Cmd.BRIGHTNESS_SPEED, clamp_raw_brightness(brightness), clamp_raw_speed(speed), 0x00, 0x00)


def build_animation_mode_report(mode: AnimationMode) -> bytes:
    return _report(Cmd.ANIMATION, int(mode), 0x00, 0x00, 0x00)


def build_reset_report() -> bytes:
    """Clear all LEDs. Required before per-key updates."""
    return build_animation_mode_report(AnimationMode.CLEAR)


def build_led_color_report(led_id: int, color: Color) -> bytes:
    r, g, b = _rgb(*color)
    return _report(Cmd.SET_LED, int(led_id) & 0xFF, r, g, b)


def _build_color_effect_report(cmd: Cmd, r: int, g: int, b: int) -> bytes:
    """[CC, cmd, AA, R, G, B] - Effect with custom color."""
    r, g, b = _rgb(r, g, b)
    return _report(cmd, COLOR_CUSTOM, r, g, b)


def _build_random_effect_report(cmd: Cmd) -> bytes:
    """[CC, cmd, 00, 00, 00, 00] - Effect with random colors."""
    return _report(cmd, 0x00, 0x00, 0x00, 0x00)


def _build_color_slot_report(cmd: Cmd, slot: int, r: int, g: int, b: int) -> bytes:
    """[CC, cmd, slot_id, R, G, B] - Set a color slot."""
    r, g, b = _rgb(r, g, b)
    slot_id = COLOR_SLOT_BASE + _clamp(slot, 0, SLOT_LIMITS[cmd] - 1)
    return _report(cmd, slot_id, r, g, b)


def build_effect_reports(effect: Ite8910Effect, colors: list[Color] | None = None) -> list[bytes]:
    """Build the full report sequence for an effect.

    Sequence per the Windows Control Center:
    1. Animation mode or color effect command
    2. Color slots (if applicable)
    3. Brightness/speed (handled separately by the caller)
    """
    colors = colors or []

    animation_effects: dict[Ite8910Effect, AnimationMode] = {
        Ite8910Effect.SPECTRUM_CYCLE: AnimationMode.SPECTRUM_CYCLE,
        Ite8910Effect.RAINBOW_WAVE: AnimationMode.RAINBOW_WAVE,
        Ite8910Effect.RANDOM: AnimationMode.RANDOM,
        Ite8910Effect.SCAN: AnimationMode.SCAN,
        Ite8910Effect.SNAKE: AnimationMode.SNAKE,
        Ite8910Effect.FN_HIGHLIGHT: AnimationMode.SPECTRUM_CYCLE,
        Ite8910Effect.OFF: AnimationMode.CLEAR,
    }

    slot_effects: dict[Ite8910Effect, tuple[AnimationMode, Cmd]] = {
        Ite8910Effect.RAINBOW_WAVE: (AnimationMode.RAINBOW_WAVE, Cmd.WAVE_COLOR),
        Ite8910Effect.SCAN: (AnimationMode.SCAN, Cmd.SCAN_COLOR),
        Ite8910Effect.SNAKE: (AnimationMode.SNAKE, Cmd.SNAKE_COLOR),
    }

    color_effects: dict[Ite8910Effect, tuple[Ite8910Effect, Cmd]] = {
        Ite8910Effect.BREATHING_COLOR: (Ite8910Effect.BREATHING, Cmd.BREATHING),
        Ite8910Effect.FLASHING_COLOR: (Ite8910Effect.FLASHING, Cmd.FLASHING),
    }

    random_effects: dict[Ite8910Effect, Cmd] = {
        Ite8910Effect.BREATHING: Cmd.BREATHING,
        Ite8910Effect.FLASHING: Cmd.FLASHING,
    }

    reports: list[bytes] = []

    if effect == Ite8910Effect.RANDOM_COLOR:
        reports.append(build_animation_mode_report(AnimationMode.RANDOM))
        if colors:
            r, g, b = colors[0]
            reports.append(_build_color_slot_report(Cmd.RANDOM_COLOR, 0, r, g, b))
    elif effect in color_effects:
        base, cmd = color_effects[effect]
        if colors:
            r, g, b = colors[0]
            reports.append(_build_color_effect_report(cmd, r, g, b))
        elif base in random_effects:
            reports.append(_build_random_effect_report(random_effects[base]))
    elif effect in random_effects:
        reports.append(_build_random_effect_report(random_effects[effect]))
    elif effect in animation_effects:
        reports.append(build_animation_mode_report(animation_effects[effect]))
        if effect in slot_effects and colors:
            _, cmd = slot_effects[effect]
            limit = SLOT_LIMITS[cmd]
            for i, (r, g, b) in enumerate(colors[:limit]):
                reports.append(_build_color_slot_report(cmd, i, r, g, b))

    return reports


# --- Legacy aliases ---

build_brightness_speed_report_raw = build_brightness_speed_report


def build_effect_report(effect: Ite8910Effect | int | str) -> bytes:
    """Legacy single-report interface."""
    reports = build_effect_reports(normalize_effect(effect))
    return reports[0] if reports else build_reset_report()


# --- Stateful interface ---

@dataclass
class Ite8910ProtocolState:
    """Tracks brightness/speed state since the firmware expects both in one command."""

    current_brightness_raw: int = 0
    current_speed_raw: int = 0

    def set_brightness_and_speed_raw(self, brightness: int, speed: int) -> bytes:
        self.current_brightness_raw = clamp_raw_brightness(brightness)
        self.current_speed_raw = clamp_raw_speed(speed)
        return build_brightness_speed_report(self.current_brightness_raw, self.current_speed_raw)

    def set_brightness_raw(self, brightness: int) -> bytes:
        return self.set_brightness_and_speed_raw(brightness, self.current_speed_raw)

    def set_speed_raw(self, speed: int) -> bytes:
        return self.set_brightness_and_speed_raw(self.current_brightness_raw, speed)

    def set_effect(self, effect: Ite8910Effect | int | str, colors: list[Color] | None = None) -> list[bytes]:
        return build_effect_reports(normalize_effect(effect), colors)

    def reset(self) -> bytes:
        return build_reset_report()

    def set_led_color(self, led_id: int, color: Color) -> bytes:
        return build_led_color_report(led_id, color)
