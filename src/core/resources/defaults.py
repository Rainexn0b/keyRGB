"""Built-in reference profile data.

Historically, KeyRGB started as a personal driver for the WootBook Y15 Pro, so
the built-in reference keymap/layout defaults are based on that model.

These defaults are used as a fallback and for first-run UX; users are expected
to calibrate their own keymap/backdrop for best accuracy.

This module intentionally keeps the *API surface* stable (the exported constants
remain the same), while keeping the large data blobs in a JSON resource file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast


_DEFAULTS_PATH = Path(__file__).resolve().parent / "reference_defaults_wootbook_y15_pro.json"
_FALLBACK_REFERENCE_ROWS = 6
_FALLBACK_REFERENCE_COLS = 21


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _load_defaults() -> dict[str, object]:
    try:
        raw = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        return _as_dict(raw)
    except Exception:
        return {}


_RAW: dict[str, object] = _load_defaults()


def _parse_row_col(text: object) -> tuple[int, int] | None:
    try:
        row_text, col_text = str(text).split(",", 1)
        return int(row_text.strip()), int(col_text.strip())
    except Exception:
        return None


DEFAULT_LAYOUT_TWEAKS: dict[str, float] = {
    "dx": 0.0,
    "dy": 0.0,
    "inset": 0.06,
    "sx": 1.0,
    "sy": 1.0,
}

_layout = _as_dict(_RAW.get("layout_tweaks"))
for _k in list(DEFAULT_LAYOUT_TWEAKS.keys()):
    _v = _layout.get(_k)
    if isinstance(_v, (int, float)):
        DEFAULT_LAYOUT_TWEAKS[_k] = float(_v)


DEFAULT_KEYMAP: dict[str, str] = {}
_keymap = _as_dict(_RAW.get("keymap"))
for _k, _v in _keymap.items():
    if isinstance(_k, str) and isinstance(_v, str):
        DEFAULT_KEYMAP[_k] = _v


def _infer_reference_matrix_dimensions() -> tuple[int, int]:
    max_row = -1
    max_col = -1
    for coord_text in DEFAULT_KEYMAP.values():
        parsed = _parse_row_col(coord_text)
        if parsed is None:
            continue
        row, col = parsed
        max_row = max(max_row, int(row))
        max_col = max(max_col, int(col))

    if max_row >= 0 and max_col >= 0:
        return max_row + 1, max_col + 1

    return _FALLBACK_REFERENCE_ROWS, _FALLBACK_REFERENCE_COLS


REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS = _infer_reference_matrix_dimensions()


DEFAULT_PER_KEY_TWEAKS: dict[str, dict[str, float]] = {}
_per_key = _as_dict(_RAW.get("per_key_tweaks"))
for _key_id, _tweaks in _per_key.items():
    if not isinstance(_key_id, str) or not isinstance(_tweaks, dict):
        continue
    _out: dict[str, float] = {}
    for _k in ("dx", "dy", "sx", "sy", "inset"):
        _v = _tweaks.get(_k)
        if isinstance(_v, (int, float)):
            _out[_k] = float(_v)
    if _out:
        DEFAULT_PER_KEY_TWEAKS[_key_id] = _out


def build_default_colors(*, num_rows: int | None = None, num_cols: int | None = None) -> dict[tuple[int, int], tuple[int, int, int]]:
    rows = REFERENCE_MATRIX_ROWS if num_rows is None else max(0, int(num_rows))
    cols = REFERENCE_MATRIX_COLS if num_cols is None else max(0, int(num_cols))
    return {(r, c): (255, 255, 255) for r in range(rows) for c in range(cols)}


DEFAULT_COLORS = build_default_colors()


__all__ = [
    "DEFAULT_LAYOUT_TWEAKS",
    "DEFAULT_KEYMAP",
    "DEFAULT_PER_KEY_TWEAKS",
    "DEFAULT_COLORS",
    "REFERENCE_MATRIX_ROWS",
    "REFERENCE_MATRIX_COLS",
    "build_default_colors",
]
