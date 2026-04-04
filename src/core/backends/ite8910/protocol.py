"""ITE 8910 HID protocol for per-key RGB keyboards.

Protocol documentation:
https://chocapikk.com/posts/2026/reverse-engineering-ite8910-keyboard-rgb/

All commands are 6-byte HID feature reports with report ID 0xCC:
  [0xCC, command, data0, data1, data2, data3]

Command reference (from reverse-engineered .NET IL and native DLL):
  0x00 XX       - Animation mode select (XX = mode ID)
  0x01 ID R G B - Set single key color
  0x09 BR SP    - Set brightness (0x00-0x0A) and speed (0x00-0x0A)
  0x0A 00       - Breathing with random colors
  0x0A AA R G B - Breathing with custom color
  0x0B 00       - Flashing with random colors
  0x0B AA R G B - Flashing with custom color
  0x15 SL R G B - Wave direction + color (SL: 0xA1-0xA8 custom, 0x71-0x78 preset)
  0x16 SL R G B - Snake direction + color (SL: 0xA1-0xA4 custom, 0x71-0x74 preset)
  0x17 SL R G B - Scan color slot (SL: 0xA1-0xA2)
  0x18 A1 R G B - Random with custom color
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from math import ceil
from typing import Iterable

from src.core.backends.ite8910._protocol_effects import EffectDesc as _EffectDesc
from src.core.backends.ite8910._protocol_effects import build_effect_reports_impl

# --- Hardware constants ---

VENDOR_ID = 0x048D
PRODUCT_ID = 0x8910
NUM_ROWS = 6
NUM_COLS = 20
UI_BRIGHTNESS_MAX = 50
RAW_BRIGHTNESS_MAX = 0x0A
RAW_SPEED_MAX = 0x0A
REPORT_ID = 0xCC
LED_ID_ROW_STRIDE = 0x20
COLOR_CUSTOM = 0xAA
COLOR_SLOT_BASE = 0xA1
PRESET_SLOT_BASE = 0x71

# Wave: 8 directions (preset 0x71-0x78, custom 0xA1-0xA8)
# Snake: 4 diagonal directions (preset 0x71-0x74, custom 0xA1-0xA4)
# Slot index encodes direction in both preset and custom ranges.
WAVE_DIRECTIONS = ("up_left", "up_right", "down_left", "down_right", "up", "down", "left", "right")
SNAKE_DIRECTIONS = ("up_left", "up_right", "down_left", "down_right")

Color = tuple[int, int, int]


# --- Enums ---


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


_EFFECTS: dict[Ite8910Effect, _EffectDesc] = {
    Ite8910Effect.SPECTRUM_CYCLE: _EffectDesc(animation=AnimationMode.SPECTRUM_CYCLE),
    Ite8910Effect.RAINBOW_WAVE: _EffectDesc(
        animation=AnimationMode.RAINBOW_WAVE,
        slot_cmd=Cmd.WAVE_COLOR,
        slot_max=1,
        directions=WAVE_DIRECTIONS,
    ),
    Ite8910Effect.BREATHING: _EffectDesc(random_cmd=Cmd.BREATHING),
    Ite8910Effect.BREATHING_COLOR: _EffectDesc(color_cmd=Cmd.BREATHING, random_cmd=Cmd.BREATHING),
    Ite8910Effect.FLASHING: _EffectDesc(random_cmd=Cmd.FLASHING),
    Ite8910Effect.FLASHING_COLOR: _EffectDesc(color_cmd=Cmd.FLASHING, random_cmd=Cmd.FLASHING),
    Ite8910Effect.RANDOM: _EffectDesc(animation=AnimationMode.RANDOM),
    Ite8910Effect.RANDOM_COLOR: _EffectDesc(
        animation=AnimationMode.RANDOM,
        slot_cmd=Cmd.RANDOM_COLOR,
        slot_max=1,
    ),
    Ite8910Effect.SCAN: _EffectDesc(
        animation=AnimationMode.SCAN,
        slot_cmd=Cmd.SCAN_COLOR,
        slot_max=2,
    ),
    Ite8910Effect.SNAKE: _EffectDesc(
        animation=AnimationMode.SNAKE,
        slot_cmd=Cmd.SNAKE_COLOR,
        slot_max=1,
        directions=SNAKE_DIRECTIONS,
    ),
    Ite8910Effect.FN_HIGHLIGHT: _EffectDesc(animation=AnimationMode.SPECTRUM_CYCLE),
    Ite8910Effect.OFF: _EffectDesc(animation=AnimationMode.CLEAR),
}


# --- Name resolution ---

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

SLOT_LIMITS: dict[Cmd, int] = {desc.slot_cmd: desc.slot_max for desc in _EFFECTS.values() if desc.slot_cmd}  # type: ignore[misc]


# --- LED IDs ---

KNOWN_LED_IDS: tuple[int, ...] = tuple(
    ((row & 0x07) << 5) | (col & 0x1F) for row in range(NUM_ROWS) for col in range(NUM_COLS)
)


# --- Clamping ---


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    return _clamp(r, 0, 0xFF), _clamp(g, 0, 0xFF), _clamp(b, 0, 0xFF)


def clamp_channel(value: int) -> int:
    return _clamp(value, 0, 0xFF)


def clamp_raw_brightness(value: int) -> int:
    return _clamp(value, 0, RAW_BRIGHTNESS_MAX)


def clamp_raw_speed(value: int) -> int:
    return _clamp(value, 0, RAW_SPEED_MAX)


# --- Conversions ---


def raw_speed_from_effect_speed(value: int) -> int:
    """Map KeyRGB's speed arg to the firmware's 0x00-0x0A scale.

    The firmware accepts 0x00 (slowest) to 0x0A (fastest).
    KeyRGB currently passes the UI speed through directly and relies on the
    backend speed policy to choose inversion or direct ordering.
    """
    try:
        return clamp_raw_speed(int(value))
    except (TypeError, ValueError):
        return 0


def raw_brightness_from_ui(value: int) -> int:
    """Map KeyRGB's 0..50 UI brightness to the firmware's 0..10 scale."""
    ui = _clamp(value, 0, UI_BRIGHTNESS_MAX)
    if ui == 0:
        return 0
    return clamp_raw_brightness(int(ceil(ui * RAW_BRIGHTNESS_MAX / UI_BRIGHTNESS_MAX)))


def ui_brightness_from_raw(value: int) -> int:
    raw = clamp_raw_brightness(value)
    if raw == 0:
        return 0
    return _clamp(round(raw / RAW_BRIGHTNESS_MAX * UI_BRIGHTNESS_MAX), 1, UI_BRIGHTNESS_MAX)


def normalize_effect(effect: Ite8910Effect | int | str) -> Ite8910Effect:
    if isinstance(effect, Ite8910Effect):
        return effect
    if isinstance(effect, str):
        key = effect.strip().lower().replace(" ", "_")
        if key in _EFFECT_NAMES:
            return _EFFECT_NAMES[key]
        msg = f"Unsupported ITE 8910 effect: {effect}"
        raise ValueError(msg)
    return Ite8910Effect(int(effect))


def led_id_from_row_col(row: int, col: int) -> int:
    """Translate KeyRGB logical `(row, col)` into the ITE8910 LED id.

    KeyRGB's saved keymaps and built-in reference profiles use a bottom-up
    logical row convention: row 0 is the bottom row and row 5 is the top row.
    The ITE8910 hardware formula numbers rows in the opposite direction, so the
    row must be flipped before encoding the LED id.
    """

    logical_row = int(row)
    hardware_row = (NUM_ROWS - 1) - logical_row
    return ((hardware_row & 0x07) << 5) | (int(col) & 0x1F)


def iter_matrix_led_ids() -> Iterable[int]:
    for row in range(NUM_ROWS):
        for col in range(NUM_COLS):
            yield led_id_from_row_col(row, col)


def iter_known_led_ids() -> Iterable[int]:
    yield from KNOWN_LED_IDS


# --- Report builders ---


def _report(*data: int) -> bytes:
    return bytes((REPORT_ID, *data))


def build_brightness_speed_report(brightness: int, speed: int) -> bytes:
    """[CC, 09, brightness, speed, 00, 00]."""
    return _report(Cmd.BRIGHTNESS_SPEED, clamp_raw_brightness(brightness), clamp_raw_speed(speed), 0x00, 0x00)


def build_animation_mode_report(mode: AnimationMode) -> bytes:
    """[CC, 00, mode, 00, 00, 00]."""
    return _report(Cmd.ANIMATION, int(mode), 0x00, 0x00, 0x00)


def build_reset_report() -> bytes:
    """[CC, 00, 0C, 00, 00, 00] - Clear all LEDs. Required before per-key updates."""
    return build_animation_mode_report(AnimationMode.CLEAR)


def build_led_color_report(led_id: int, color: Color) -> bytes:
    """[CC, 01, led_id, R, G, B]."""
    r, g, b = _rgb(*color)
    return _report(Cmd.SET_LED, int(led_id) & 0xFF, r, g, b)


def build_effect_reports(
    effect: Ite8910Effect,
    colors: list[Color] | None = None,
    direction: str | None = None,
) -> list[bytes]:
    return build_effect_reports_impl(
        effect,
        effects=_EFFECTS,
        colors=colors,
        direction=direction,
        build_animation_mode_report=build_animation_mode_report,
        report=_report,
        rgb=_rgb,
        color_custom=COLOR_CUSTOM,
        color_slot_base=COLOR_SLOT_BASE,
        preset_slot_base=PRESET_SLOT_BASE,
    )


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

    def set_effect(
        self,
        effect: Ite8910Effect | int | str,
        colors: list[Color] | None = None,
        direction: str | None = None,
    ) -> list[bytes]:
        return build_effect_reports(normalize_effect(effect), colors, direction)

    def reset(self) -> bytes:
        return build_reset_report()

    def set_led_color(self, led_id: int, color: Color) -> bytes:
        return build_led_color_report(led_id, color)
