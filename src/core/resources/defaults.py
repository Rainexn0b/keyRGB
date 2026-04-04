"""Built-in reference profile data.

The built-in reference keymap/layout defaults are organized by physical layout
variant. ANSI is the canonical baseline because the historical curated manual
mapping already reflects an ANSI keyboard.

These defaults are used as a fallback and for first-run UX; users are expected
to calibrate their own keymap/backdrop for best accuracy.

This module intentionally keeps the legacy ANSI constants available while also
exposing layout-aware accessors for newer UI flows.
"""

from __future__ import annotations

from functools import lru_cache
from typing import cast

from src.core.resources.layouts import resolve_layout_id
from src.core.resources.reference_defaults_specs import load_reference_defaults_spec


_DEFAULT_LAYOUT_ID = "ansi"
_SUPPORTED_LAYOUT_IDS = {"ansi", "iso", "ks", "abnt", "jis"}
_FALLBACK_REFERENCE_ROWS = 6
_FALLBACK_REFERENCE_COLS = 21


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _normalize_layout_id(layout_id: str | None) -> str:
    value = str(layout_id or _DEFAULT_LAYOUT_ID).strip().lower()
    if value == "auto":
        value = resolve_layout_id(value)
    return value if value in _SUPPORTED_LAYOUT_IDS else _DEFAULT_LAYOUT_ID


@lru_cache(maxsize=None)
def _load_defaults(layout_id: str = _DEFAULT_LAYOUT_ID) -> dict[str, object]:
    resolved_layout = _normalize_layout_id(layout_id)
    spec_defaults = load_reference_defaults_spec(resolved_layout)
    if spec_defaults:
        return _as_dict(spec_defaults)

    if resolved_layout != _DEFAULT_LAYOUT_ID:
        ansi_defaults = load_reference_defaults_spec(_DEFAULT_LAYOUT_ID)
        if ansi_defaults:
            return _as_dict(ansi_defaults)

    return {}


def _parse_layout_tweaks(raw: dict[str, object]) -> dict[str, float]:
    out: dict[str, float] = {
        "dx": 0.0,
        "dy": 0.0,
        "inset": 0.06,
        "sx": 1.0,
        "sy": 1.0,
    }
    layout = _as_dict(raw.get("layout_tweaks"))
    for key in list(out.keys()):
        value = layout.get(key)
        if isinstance(value, (int, float)):
            out[key] = float(value)
    return out


def _parse_keymap(raw: dict[str, object]) -> dict[str, str]:
    out: dict[str, str] = {}
    keymap = _as_dict(raw.get("keymap"))
    for key, value in keymap.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def _parse_row_col(text: object) -> tuple[int, int] | None:
    try:
        row_text, col_text = str(text).split(",", 1)
        return int(row_text.strip()), int(col_text.strip())
    except ValueError:
        return None


def get_default_layout_tweaks(layout_id: str | None = None) -> dict[str, float]:
    return dict(_parse_layout_tweaks(_load_defaults(_normalize_layout_id(layout_id))))


def get_default_keymap(layout_id: str | None = None) -> dict[str, str]:
    return dict(_parse_keymap(_load_defaults(_normalize_layout_id(layout_id))))


def _infer_reference_matrix_dimensions(keymap: dict[str, str]) -> tuple[int, int]:
    max_row = -1
    max_col = -1
    for coord_text in keymap.values():
        parsed = _parse_row_col(coord_text)
        if parsed is None:
            continue
        row, col = parsed
        max_row = max(max_row, int(row))
        max_col = max(max_col, int(col))

    if max_row >= 0 and max_col >= 0:
        return max_row + 1, max_col + 1

    return _FALLBACK_REFERENCE_ROWS, _FALLBACK_REFERENCE_COLS


def get_reference_matrix_dimensions(layout_id: str | None = None) -> tuple[int, int]:
    return _infer_reference_matrix_dimensions(get_default_keymap(layout_id))


def get_default_per_key_tweaks(layout_id: str | None = None) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    per_key = _as_dict(_load_defaults(_normalize_layout_id(layout_id)).get("per_key_tweaks"))
    for key_id, tweaks in per_key.items():
        if not isinstance(key_id, str) or not isinstance(tweaks, dict):
            continue
        parsed: dict[str, float] = {}
        for tweak_key in ("dx", "dy", "sx", "sy", "inset"):
            value = tweaks.get(tweak_key)
            if isinstance(value, (int, float)):
                parsed[tweak_key] = float(value)
        if parsed:
            out[key_id] = parsed
    return out


def get_default_lightbar_overlay() -> dict[str, bool | float]:
    return {
        "visible": True,
        "length": 0.72,
        "thickness": 0.12,
        "dx": 0.0,
        "dy": 0.0,
        "inset": 0.04,
    }


DEFAULT_LAYOUT_TWEAKS = get_default_layout_tweaks(_DEFAULT_LAYOUT_ID)
DEFAULT_KEYMAP = get_default_keymap(_DEFAULT_LAYOUT_ID)
REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS = get_reference_matrix_dimensions(_DEFAULT_LAYOUT_ID)
DEFAULT_PER_KEY_TWEAKS = get_default_per_key_tweaks(_DEFAULT_LAYOUT_ID)
DEFAULT_LIGHTBAR_OVERLAY = get_default_lightbar_overlay()


def build_default_colors(
    *, num_rows: int | None = None, num_cols: int | None = None
) -> dict[tuple[int, int], tuple[int, int, int]]:
    rows = REFERENCE_MATRIX_ROWS if num_rows is None else max(0, int(num_rows))
    cols = REFERENCE_MATRIX_COLS if num_cols is None else max(0, int(num_cols))
    return {(r, c): (255, 255, 255) for r in range(rows) for c in range(cols)}


DEFAULT_COLORS = build_default_colors()


__all__ = [
    "DEFAULT_LAYOUT_TWEAKS",
    "DEFAULT_KEYMAP",
    "DEFAULT_PER_KEY_TWEAKS",
    "DEFAULT_COLORS",
    "DEFAULT_LIGHTBAR_OVERLAY",
    "REFERENCE_MATRIX_ROWS",
    "REFERENCE_MATRIX_COLS",
    "build_default_colors",
    "get_default_lightbar_overlay",
    "get_default_keymap",
    "get_default_layout_tweaks",
    "get_default_per_key_tweaks",
    "get_reference_matrix_dimensions",
]
