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

    from ._layout_components import build_alpha_block, build_arrow_cluster, build_function_rows, build_numpad

    unit = 40
    gap = 6

    x0 = 40
    y0 = 110

    r0 = y0
    r1 = y0 + (unit + 12)
    r2 = r1 + (unit + 10)
    r3 = r2 + (unit + 10)
    r4 = r3 + (unit + 10)

    nav_x0 = 700
    nav_aux_x0 = 856
    nx0 = 806

    keys: List[KeyDef] = []

    fy = r0 - 66
    row_tops = {
        "number": r0,
        "top": r1,
        "home": r2,
        "shift": r3,
        "bottom": r4,
    }

    keys += build_function_rows(fy=fy, x0=x0, nav_x0=nav_x0, nav_aux_x0=nav_aux_x0)
    keys += build_alpha_block(spec=spec, x0=x0, unit=unit, gap=gap, row_tops=row_tops)

    arrow_unit = 30
    ax0 = 700
    ay0 = r4 + 26
    keys += build_arrow_cluster(ax0=ax0, ay0=ay0, arrow_unit=arrow_unit)
    keys += build_numpad(r0=r0, r1=r1, r2=r2, r3=r3, r4=r4, nx0=nx0, unit=unit, gap=gap)

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
