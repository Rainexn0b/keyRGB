"""Reference keyboard layout definitions.

This is a *visual* layout used to draw clickable key hitboxes on top of the
bundled reference deck image (historically the WootBook Y15 Pro image).

Important: The ITE controller exposes a 6×21 LED matrix (row,col). The mapping
between a physical key and a matrix coordinate is device-specific and must be
calibrated.

Coordinates in this file are in the source image coordinate space:
- Image size: 1008×450
- Each key has a rectangle: (x, y, w, h)

The rectangles are intentionally approximate; calibration fixes functional
mapping even if the boxes are slightly off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple, cast


BASE_IMAGE_SIZE: Tuple[int, int] = (1008, 450)


@dataclass(frozen=True)
class KeyDef:
    key_id: str
    label: str
    rect: Tuple[int, int, int, int]  # x, y, w, h in BASE_IMAGE_SIZE coords


def _units_row(y: int, x0: int, unit: int, gap: int, keys: Iterable[Tuple[str, str, float]]) -> List[KeyDef]:
    out: List[KeyDef] = []
    x = x0
    for key_id, label, w_units in keys:
        w = int(round(w_units * unit + (w_units - 1) * 0))
        out.append(KeyDef(key_id=key_id, label=label, rect=(x, y, w, unit)))
        x += w + gap
    return out


def _units_row_with_spacers(
    y: int,
    x0: int,
    unit: int,
    gap: int,
    items: Iterable[Tuple[str, str, float] | Tuple[None, None, float]],
) -> List[KeyDef]:
    """Row helper that supports spacer runs.

    Use (None, None, width_units) to advance x without creating a key.
    """

    out: List[KeyDef] = []
    x = x0
    for key_id, label, w_units in items:
        if key_id is None:
            x += int(round(w_units * unit))
            continue

        key_id_str = cast(str, key_id)
        label_str = cast(str, label)
        w = int(round(w_units * unit))
        out.append(KeyDef(key_id=key_id_str, label=label_str, rect=(x, y, w, unit)))
        x += w + gap
    return out


def build_layout() -> List[KeyDef]:
    """Return the built-in reference layout (full-size-with-numpad)."""

    unit = 40
    gap = 6

    x0 = 40
    y0 = 110

    r0 = y0
    r1 = y0 + (unit + 12)
    r2 = r1 + (unit + 10)
    r3 = r2 + (unit + 10)
    r4 = r3 + (unit + 10)

    nav_x0 = 748
    nx0 = 806

    keys: List[KeyDef] = []

    fy = r0 - 66
    f_unit = 34
    f_gap = 6
    keys += _units_row_with_spacers(
        fy,
        x0,
        f_unit,
        f_gap,
        [
            ("esc", "Esc", 1.05),
            (None, None, 0.45),
            ("f1", "F1", 1),
            ("f2", "F2", 1),
            ("f3", "F3", 1),
            ("f4", "F4", 1),
            (None, None, 0.35),
            ("f5", "F5", 1),
            ("f6", "F6", 1),
            ("f7", "F7", 1),
            ("f8", "F8", 1),
            (None, None, 0.35),
            ("f9", "F9", 1),
            ("f10", "F10", 1),
            ("f11", "F11", 1),
            ("f12", "F12", 1),
        ],
    )

    keys += _units_row(
        fy + 30,
        nav_x0,
        32,
        8,
        [
            ("sc", "Sc", 1),
            ("prtsc", "PrtSc", 1),
            ("del", "Del", 1),
        ],
    )

    keys += _units_row(
        fy + 30,
        nx0,
        32,
        8,
        [
            ("home", "Home", 1),
            ("pgup", "PgUp", 1),
            ("pgdn", "PgDn", 1),
            ("end", "End", 1),
        ],
    )

    keys += _units_row(
        r0,
        x0,
        unit,
        gap,
        [
            ("grave", "`", 1),
            ("1", "1", 1),
            ("2", "2", 1),
            ("3", "3", 1),
            ("4", "4", 1),
            ("5", "5", 1),
            ("6", "6", 1),
            ("7", "7", 1),
            ("8", "8", 1),
            ("9", "9", 1),
            ("0", "0", 1),
            ("minus", "-", 1),
            ("equal", "=", 1),
            ("backspace", "Bksp", 2.15),
        ],
    )

    keys += _units_row(
        r1,
        x0,
        unit,
        gap,
        [
            ("tab", "Tab", 1.5),
            ("q", "Q", 1),
            ("w", "W", 1),
            ("e", "E", 1),
            ("r", "R", 1),
            ("t", "T", 1),
            ("y", "Y", 1),
            ("u", "U", 1),
            ("i", "I", 1),
            ("o", "O", 1),
            ("p", "P", 1),
            ("lbracket", "[", 1),
            ("rbracket", "]", 1),
            ("bslash", "\\", 1.65),
        ],
    )

    keys += _units_row(
        r2,
        x0,
        unit,
        gap,
        [
            ("caps", "Caps", 1.75),
            ("a", "A", 1),
            ("s", "S", 1),
            ("d", "D", 1),
            ("f", "F", 1),
            ("g", "G", 1),
            ("h", "H", 1),
            ("j", "J", 1),
            ("k", "K", 1),
            ("l", "L", 1),
            ("semicolon", ";", 1),
            ("quote", "'", 1),
            ("enter", "Enter", 2.35),
        ],
    )

    keys += _units_row(
        r3,
        x0,
        unit,
        gap,
        [
            ("lshift", "Shift", 2.25),
            ("z", "Z", 1),
            ("x", "X", 1),
            ("c", "C", 1),
            ("v", "V", 1),
            ("b", "B", 1),
            ("n", "N", 1),
            ("m", "M", 1),
            ("comma", ",", 1),
            ("dot", ".", 1),
            ("slash", "/", 1),
            ("rshift", "Shift", 2.85),
        ],
    )

    keys += _units_row(
        r4,
        x0,
        unit,
        gap,
        [
            ("lctrl", "Ctrl", 1.25),
            ("fn", "Fn", 1.0),
            ("lwin", "Win", 1.0),
            ("lalt", "Alt", 1.25),
            ("space", "Space", 6.45),
            ("ralt", "Alt", 1.25),
            ("menu", "Copilot", 1.0),
        ],
    )

    arrow_unit = 34
    ax0 = 642
    ay0 = r4 + 10
    keys += [
        KeyDef("up", "↑", (ax0 + arrow_unit + 6, ay0 - arrow_unit - 6, arrow_unit, arrow_unit)),
        KeyDef("left", "←", (ax0, ay0, arrow_unit, arrow_unit)),
        KeyDef("down", "↓", (ax0 + arrow_unit + 6, ay0, arrow_unit, arrow_unit)),
        KeyDef("right", "→", (ax0 + 2 * (arrow_unit + 6), ay0, arrow_unit, arrow_unit)),
    ]

    keys += _units_row(
        r0,
        nx0,
        unit,
        gap,
        [
            ("numlock", "Num", 1),
            ("numslash", "/", 1),
            ("numstar", "*", 1),
            ("numminus", "-", 1),
        ],
    )
    keys += _units_row(r1, nx0, unit, gap, [("num7", "7", 1), ("num8", "8", 1), ("num9", "9", 1)])
    keys += _units_row(r2, nx0, unit, gap, [("num4", "4", 1), ("num5", "5", 1), ("num6", "6", 1)])
    keys += _units_row(r3, nx0, unit, gap, [("num1", "1", 1), ("num2", "2", 1), ("num3", "3", 1)])
    keys += _units_row(r4, nx0, unit, gap, [("num0", "0", 2.0), ("numdot", ".", 1)])

    plus_x = nx0 + 3 * (unit + gap)
    plus_y = r1
    plus_h = 2 * unit + gap
    keys.append(KeyDef("numplus", "+", (plus_x, plus_y, unit, plus_h)))

    ent_x = nx0 + 3 * (unit + gap)
    ent_y = r3
    ent_h = 2 * unit + gap
    keys.append(KeyDef("numenter", "Ent", (ent_x, ent_y, unit, ent_h)))

    return keys


REFERENCE_DEVICE_KEYS: List[KeyDef] = build_layout()
