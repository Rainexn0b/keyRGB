"""Reference keyboard layout definitions.

This is a *visual* layout used to draw clickable key hitboxes on top of the
bundled reference deck image (historically the WootBook Y15 Pro image).

Important: KeyRGB's reference profiles historically used a 6×21 Tongfang-style
matrix, but actual backend dimensions vary by controller. The mapping between a
physical key and a matrix coordinate is device-specific and must be calibrated.

Coordinates in this file are in the source image coordinate space:
- Image size: 1008×450
- Each key has a rectangle: (x, y, w, h)

The rectangles are intentionally approximate; calibration fixes functional
mapping even if the boxes are slightly off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple, cast

from .layout_specs import load_layout_spec


BASE_IMAGE_SIZE: Tuple[int, int] = (1008, 450)


@dataclass(frozen=True)
class KeyDef:
    key_id: str
    label: str
    rect: Tuple[int, int, int, int]  # x, y, w, h in BASE_IMAGE_SIZE coords
    slot_id: str | None = None
    shape_segments: Tuple[Tuple[float, float, float, float], ...] | None = None

    def __post_init__(self) -> None:
        if not self.slot_id:
            object.__setattr__(self, "slot_id", str(self.key_id))


def _make_slot_id(prefix: str, index: int) -> str:
    return f"{prefix}_{int(index):02d}"


def _units_row(
    y: int,
    x0: int,
    unit: int,
    gap: int,
    keys: Iterable[Tuple[str, str, float]],
    *,
    slot_prefix: str,
) -> List[KeyDef]:
    out: List[KeyDef] = []
    x = x0
    for index, (key_id, label, w_units) in enumerate(keys):
        w = int(round(w_units * unit + (w_units - 1) * 0))
        out.append(
            KeyDef(
                key_id=key_id,
                label=label,
                rect=(x, y, w, unit),
                slot_id=_make_slot_id(slot_prefix, index),
            )
        )
        x += w + gap
    return out


def _units_row_with_spacers(
    y: int,
    x0: int,
    unit: int,
    gap: int,
    items: Iterable[Tuple[str, str, float, str | None] | Tuple[None, None, float, None]],
    *,
    slot_prefix: str,
) -> List[KeyDef]:
    """Row helper that supports spacer runs.

    Use (None, None, width_units) to advance x without creating a key.
    """

    out: List[KeyDef] = []
    x = x0
    slot_index = 0
    for key_id, label, w_units, slot_id in items:
        if key_id is None:
            x += int(round(w_units * unit))
            continue

        key_id_str = cast(str, key_id)
        label_str = cast(str, label)
        w = int(round(w_units * unit))
        out.append(
            KeyDef(
                key_id=key_id_str,
                label=label_str,
                rect=(x, y, w, unit),
                slot_id=slot_id or _make_slot_id(slot_prefix, slot_index),
            )
        )
        slot_index += 1
        x += w + gap
    return out


def _segmented_key(
    key_id: str,
    label: str,
    segments: Iterable[Tuple[int, int, int, int]],
    *,
    slot_id: str | None = None,
) -> KeyDef:
    segment_list = list(segments)
    if not segment_list:
        return KeyDef(key_id=key_id, label=label, rect=(0, 0, 0, 0), slot_id=slot_id)

    left = min(x for x, _y, _w, _h in segment_list)
    top = min(y for _x, y, _w, _h in segment_list)
    right = max(x + w for x, _y, w, _h in segment_list)
    bottom = max(y + h for _x, y, _w, h in segment_list)
    width = max(1, right - left)
    height = max(1, bottom - top)

    normalized_segments = tuple(
        (
            float(x - left) / float(width),
            float(y - top) / float(height),
            float(w) / float(width),
            float(h) / float(height),
        )
        for x, y, w, h in segment_list
    )
    return KeyDef(
        key_id=key_id,
        label=label,
        rect=(left, top, width, height),
        slot_id=slot_id,
        shape_segments=normalized_segments,
    )


LAYOUT_VARIANTS: frozenset[str] = frozenset({"ansi", "iso", "ks", "abnt", "jis"})

ISO_ONLY_KEY_IDS: frozenset[str] = frozenset({"nonusbackslash", "nonushash"})
"""Key IDs that exist on ISO-style alpha blocks and derived variants."""


def _normalize_layout_variant(variant: str | None) -> str:
    normalized = str(variant or "iso").strip().lower()
    return normalized if normalized in LAYOUT_VARIANTS else "iso"


def _end_x(keys: List[KeyDef]) -> int:
    if not keys:
        return 0
    last = keys[-1]
    return int(last.rect[0] + last.rect[2])


def _layout_row_items(
    spec: dict[str, object], row_name: str
) -> List[Tuple[str, str, float, str | None] | Tuple[None, None, float, None]]:
    rows = spec.get("rows")
    if not isinstance(rows, dict):
        return []
    raw_items = rows.get(row_name)
    if not isinstance(raw_items, list):
        return []

    out: List[Tuple[str, str, float, str | None] | Tuple[None, None, float, None]] = []
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


def _shape_segments_from_spec(raw_segments: object) -> Tuple[Tuple[float, float, float, float], ...] | None:
    if not isinstance(raw_segments, list):
        return None

    segments: list[Tuple[float, float, float, float]] = []
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


def build_layout(*, variant: str | None = None, include_iso: bool | None = None) -> List[KeyDef]:
    """Return the built-in reference layout.

    ``variant`` selects a concrete physical keyboard family. Supported values
    are ``"ansi"``, ``"iso"``, ``"ks"``, ``"abnt"``, and ``"jis"``.

    ``include_iso`` is kept for backward compatibility with older ANSI/ISO-only
    callers. When provided without an explicit ``variant``, ``False`` maps to
    ``"ansi"`` and ``True`` maps to ``"iso"``.
    """

    if variant is None and include_iso is not None:
        variant = "iso" if include_iso else "ansi"
    variant = _normalize_layout_variant(variant)
    spec = load_layout_spec(variant) or load_layout_spec("iso")

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
        [
            ("sc", "Sc", 1),
            ("prtsc", "PrtSc", 1),
            ("del", "Del", 1),
        ],
        slot_prefix="nav",
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
        slot_prefix="navaux",
    )

    number_row = _units_row_with_spacers(r0, x0, unit, gap, _layout_row_items(spec, "number"), slot_prefix="number")
    keys += number_row

    top_row = _units_row_with_spacers(r1, x0, unit, gap, _layout_row_items(spec, "top"), slot_prefix="top")
    keys += top_row

    home_row = _units_row_with_spacers(r2, x0, unit, gap, _layout_row_items(spec, "home"), slot_prefix="home")
    keys += home_row

    row_lookup = {
        "number": number_row,
        "top": top_row,
        "home": home_row,
    }
    row_top_lookup = {
        "number": r0,
        "top": r1,
        "home": r2,
        "shift": r3,
        "bottom": r4,
    }
    keys += _layout_special_keys(spec, row_lookup=row_lookup, row_top_lookup=row_top_lookup, unit=unit, gap=gap)

    shift_row = _units_row_with_spacers(r3, x0, unit, gap, _layout_row_items(spec, "shift"), slot_prefix="shift")
    keys += shift_row
    row_lookup["shift"] = shift_row

    bottom_row = _units_row_with_spacers(r4, x0, unit, gap, _layout_row_items(spec, "bottom"), slot_prefix="bottom")
    keys += bottom_row
    row_lookup["bottom"] = bottom_row

    arrow_unit = 34
    ax0 = 642
    ay0 = r4 + 10
    keys += [
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
        slot_prefix="numpad",
    )
    keys += _units_row(r1, nx0, unit, gap, [("num7", "7", 1), ("num8", "8", 1), ("num9", "9", 1)], slot_prefix="numpad1")
    keys += _units_row(r2, nx0, unit, gap, [("num4", "4", 1), ("num5", "5", 1), ("num6", "6", 1)], slot_prefix="numpad2")
    keys += _units_row(r3, nx0, unit, gap, [("num1", "1", 1), ("num2", "2", 1), ("num3", "3", 1)], slot_prefix="numpad3")
    keys += _units_row(r4, nx0, unit, gap, [("num0", "0", 2.0), ("numdot", ".", 1)], slot_prefix="numpad4")

    plus_x = nx0 + 3 * (unit + gap)
    plus_y = r1
    plus_h = 2 * unit + gap
    keys.append(KeyDef("numplus", "+", (plus_x, plus_y, unit, plus_h), slot_id="numpad_plus"))

    ent_x = nx0 + 3 * (unit + gap)
    ent_y = r3
    ent_h = 2 * unit + gap
    keys.append(KeyDef("numenter", "Ent", (ent_x, ent_y, unit, ent_h), slot_id="numpad_enter"))

    return keys


def _build_reference_device_keys() -> List[KeyDef]:
    out: List[KeyDef] = []
    seen: set[str] = set()
    for variant_name in ("iso", "ansi", "ks", "abnt", "jis"):
        for key in build_layout(variant=variant_name):
            if key.key_id in seen:
                continue
            out.append(key)
            seen.add(key.key_id)
    return out


# Superset used by backends and overlay helpers that need a stable key-id index.
REFERENCE_DEVICE_KEYS: List[KeyDef] = _build_reference_device_keys()


def get_layout_keys(
    physical_layout: str = "auto",
    *,
    legend_pack_id: str | None = None,
    slot_overrides: dict[str, dict[str, object]] | None = None,
) -> List[KeyDef]:
    """Return the reference layout key list for *physical_layout*.

    Delegates to :mod:`src.core.resources.layouts` for catalog resolution.
    ``"auto"`` probes sysfs; other values are looked up in the layout catalog.
    """

    from .layouts import get_layout_keys as _get

    return _get(physical_layout, legend_pack_id=legend_pack_id, slot_overrides=slot_overrides)


def resolve_physical_layout(physical_layout: str) -> str:
    """Resolve *physical_layout* to a concrete, non-``"auto"`` layout ID.

    Delegates to :mod:`src.core.resources.layouts` for catalog resolution.
    """

    from .layouts import resolve_layout_id

    return resolve_layout_id(physical_layout)


def slot_id_for_key_id(physical_layout: str, key_id: str) -> str | None:
    from .layouts import slot_id_for_key_id as _slot_id_for_key_id

    return _slot_id_for_key_id(physical_layout, key_id)


def key_id_for_slot_id(physical_layout: str, slot_id: str) -> str | None:
    from .layouts import key_id_for_slot_id as _key_id_for_slot_id

    return _key_id_for_slot_id(physical_layout, slot_id)
