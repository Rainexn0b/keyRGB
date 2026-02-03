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


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _load_defaults() -> dict[str, object]:
    try:
        raw = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        return _as_dict(raw)
    except Exception:
        return {}


_RAW: dict[str, object] = _load_defaults()


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


# Generate default colors (all white)
DEFAULT_COLORS = {(r, c): (255, 255, 255) for r in range(6) for c in range(21)}


__all__ = [
    "DEFAULT_LAYOUT_TWEAKS",
    "DEFAULT_KEYMAP",
    "DEFAULT_PER_KEY_TWEAKS",
    "DEFAULT_COLORS",
]
