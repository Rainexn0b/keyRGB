"""Internal helpers for building the reference keyboard layout."""

from __future__ import annotations

from typing import List

from .layout import KeyDef, _end_x, _make_slot_id, _units_row, _units_row_with_spacers


def _layout_row_items(
    spec: dict[str, object], row_name: str
) -> list[tuple[str, str, float, str | None] | tuple[None, None, float, None]]:
    rows = spec.get("rows")
    if not isinstance(rows, dict):
        return []
    raw_items = rows.get(row_name)
    if not isinstance(raw_items, list):
        return []

    out: list[tuple[str, str, float, str | None] | tuple[None, None, float, None]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        if "spacer" in raw_item:
            spacer = raw_item.get("spacer")
            if isinstance(spacer, (int, float)):
                out.append((None, None, float(spacer), None))
            continue

        key_id = raw_item.get("key_id")
        label = raw_item.get("label")
        width = raw_item.get("width")
        slot_id = raw_item.get("slot_id")
        if isinstance(key_id, str) and isinstance(label, str) and isinstance(width, (int, float)):
            out.append((key_id, label, float(width), str(slot_id) if isinstance(slot_id, str) else None))
    return out


def _shape_segments_from_spec(raw_segments: object) -> tuple[tuple[float, float, float, float], ...] | None:
    if not isinstance(raw_segments, list):
        return None

    segments: list[tuple[float, float, float, float]] = []
    for raw_segment in raw_segments:
        if not isinstance(raw_segment, list | tuple) or len(raw_segment) != 4:
            continue
        x, y, w, h = raw_segment
        if all(isinstance(value, (int, float)) for value in (x, y, w, h)):
            segments.append((float(x), float(y), float(w), float(h)))
    return tuple(segments) if segments else None


def _layout_special_keys(
    spec: dict[str, object],
    *,
    row_lookup: dict[str, List[KeyDef]],
    row_top_lookup: dict[str, int],
    unit: int,
    gap: int,
) -> List[KeyDef]:
    raw_special_keys = spec.get("special_keys")
    if not isinstance(raw_special_keys, list):
        return []

    out: List[KeyDef] = []
    for index, raw_key in enumerate(raw_special_keys):
        if not isinstance(raw_key, dict):
            continue
        key_id = raw_key.get("key_id")
        label = raw_key.get("label")
        anchor_after_row = raw_key.get("anchor_after_row")
        y_row = raw_key.get("y_row")
        width = raw_key.get("width")
        height_rows = raw_key.get("height_rows")
        dx = raw_key.get("dx", 0)
        dy = raw_key.get("dy", 0)
        slot_id = raw_key.get("slot_id")

        if not (
            isinstance(key_id, str)
            and isinstance(label, str)
            and isinstance(anchor_after_row, str)
            and isinstance(y_row, str)
            and isinstance(width, (int, float))
            and isinstance(height_rows, int)
            and isinstance(dx, (int, float))
            and isinstance(dy, (int, float))
        ):
            continue

        anchor_row = row_lookup.get(anchor_after_row, [])
        y_base = row_top_lookup.get(y_row)
        if y_base is None:
            continue

        rect = (
            _end_x(anchor_row) + gap + int(round(float(dx))),
            y_base + int(round(float(dy))),
            int(round(float(width) * unit)),
            max(1, int(height_rows) * unit + (max(1, int(height_rows)) - 1) * gap),
        )
        out.append(
            KeyDef(
                key_id=key_id,
                label=label,
                rect=rect,
                slot_id=(str(slot_id) if isinstance(slot_id, str) else _make_slot_id(f"{y_row}_special", index)),
                shape_segments=_shape_segments_from_spec(raw_key.get("shape_segments")),
            )
        )
    return out


def build_function_rows(*, fy: int, x0: int, nav_x0: int, nx0: int) -> List[KeyDef]:
    keys: List[KeyDef] = []
    f_unit = 34
    f_gap = 6
    keys += _units_row_with_spacers(
        fy,
        x0,
        f_unit,
        f_gap,
        [
            ("esc", "Esc", 1.05, None),
            (None, None, 0.45, None),
            ("f1", "F1", 1, None),
            ("f2", "F2", 1, None),
            ("f3", "F3", 1, None),
            ("f4", "F4", 1, None),
            (None, None, 0.35, None),
            ("f5", "F5", 1, None),
            ("f6", "F6", 1, None),
            ("f7", "F7", 1, None),
            ("f8", "F8", 1, None),
            (None, None, 0.35, None),
            ("f9", "F9", 1, None),
            ("f10", "F10", 1, None),
            ("f11", "F11", 1, None),
            ("f12", "F12", 1, None),
        ],
        slot_prefix="frow",
    )

    keys += _units_row(
        fy + 30,
        nav_x0,
        32,
        8,
        [("sc", "Sc", 1), ("prtsc", "PrtSc", 1), ("del", "Del", 1)],
        slot_prefix="nav",
    )
    keys += _units_row(
        fy + 30,
        nx0,
        32,
        8,
        [("home", "Home", 1), ("pgup", "PgUp", 1), ("pgdn", "PgDn", 1), ("end", "End", 1)],
        slot_prefix="navaux",
    )
    return keys


def build_alpha_block(
    *, spec: dict[str, object], x0: int, unit: int, gap: int, row_tops: dict[str, int]
) -> List[KeyDef]:
    keys: List[KeyDef] = []

    number_row = _units_row_with_spacers(
        row_tops["number"], x0, unit, gap, _layout_row_items(spec, "number"), slot_prefix="number"
    )
    top_row = _units_row_with_spacers(row_tops["top"], x0, unit, gap, _layout_row_items(spec, "top"), slot_prefix="top")
    home_row = _units_row_with_spacers(
        row_tops["home"], x0, unit, gap, _layout_row_items(spec, "home"), slot_prefix="home"
    )

    keys += number_row
    keys += top_row
    keys += home_row

    row_lookup = {"number": number_row, "top": top_row, "home": home_row}
    keys += _layout_special_keys(spec, row_lookup=row_lookup, row_top_lookup=row_tops, unit=unit, gap=gap)

    shift_row = _units_row_with_spacers(
        row_tops["shift"], x0, unit, gap, _layout_row_items(spec, "shift"), slot_prefix="shift"
    )
    bottom_row = _units_row_with_spacers(
        row_tops["bottom"], x0, unit, gap, _layout_row_items(spec, "bottom"), slot_prefix="bottom"
    )
    keys += shift_row
    keys += bottom_row
    return keys


def build_arrow_cluster(*, ax0: int, ay0: int, arrow_unit: int) -> List[KeyDef]:
    return [
        KeyDef(
            "up",
            "↑",
            (ax0 + arrow_unit + 6, ay0 - arrow_unit - 6, arrow_unit, arrow_unit),
            slot_id="arrow_up",
        ),
        KeyDef("left", "←", (ax0, ay0, arrow_unit, arrow_unit), slot_id="arrow_left"),
        KeyDef("down", "↓", (ax0 + arrow_unit + 6, ay0, arrow_unit, arrow_unit), slot_id="arrow_down"),
        KeyDef("right", "→", (ax0 + 2 * (arrow_unit + 6), ay0, arrow_unit, arrow_unit), slot_id="arrow_right"),
    ]


def build_numpad(*, r0: int, r1: int, r2: int, r3: int, r4: int, nx0: int, unit: int, gap: int) -> List[KeyDef]:
    keys: List[KeyDef] = []
    keys += _units_row(
        r0,
        nx0,
        unit,
        gap,
        [("numlock", "Num", 1), ("numslash", "/", 1), ("numstar", "*", 1), ("numminus", "-", 1)],
        slot_prefix="numpad",
    )
    keys += _units_row(
        r1, nx0, unit, gap, [("num7", "7", 1), ("num8", "8", 1), ("num9", "9", 1)], slot_prefix="numpad1"
    )
    keys += _units_row(
        r2, nx0, unit, gap, [("num4", "4", 1), ("num5", "5", 1), ("num6", "6", 1)], slot_prefix="numpad2"
    )
    keys += _units_row(
        r3, nx0, unit, gap, [("num1", "1", 1), ("num2", "2", 1), ("num3", "3", 1)], slot_prefix="numpad3"
    )
    keys += _units_row(r4, nx0, unit, gap, [("num0", "0", 2.0), ("numdot", ".", 1)], slot_prefix="numpad4")

    plus_x = nx0 + 3 * (unit + gap)
    plus_h = 2 * unit + gap
    keys.append(KeyDef("numplus", "+", (plus_x, r1, unit, plus_h), slot_id="numpad_plus"))

    ent_x = nx0 + 3 * (unit + gap)
    ent_h = 2 * unit + gap
    keys.append(KeyDef("numenter", "Ent", (ent_x, r3, unit, ent_h), slot_id="numpad_enter"))
    return keys
