"""Default profile data for Y15 Pro.

This module intentionally keeps the *API surface* stable (the exported constants
remain the same), while moving the huge data blobs into a JSON resource file to
make the codebase easier to maintain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "defaults_y15_pro.json"


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_defaults() -> Dict[str, Any]:
    try:
        return json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


_RAW = _load_defaults()


DEFAULT_LAYOUT_TWEAKS: Dict[str, float] = {
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


DEFAULT_KEYMAP: Dict[str, str] = {}
_keymap = _as_dict(_RAW.get("keymap"))
for _k, _v in _keymap.items():
    if isinstance(_k, str) and isinstance(_v, str):
        DEFAULT_KEYMAP[_k] = _v


DEFAULT_PER_KEY_TWEAKS: Dict[str, Dict[str, float]] = {}
_per_key = _as_dict(_RAW.get("per_key_tweaks"))
for _key_id, _tweaks in _per_key.items():
    if not isinstance(_key_id, str) or not isinstance(_tweaks, dict):
        continue
    _out: Dict[str, float] = {}
    for _k in ("dx", "dy", "sx", "sy", "inset"):
        _v = _tweaks.get(_k)
        if isinstance(_v, (int, float)):
            _out[_k] = float(_v)
    if _out:
        DEFAULT_PER_KEY_TWEAKS[_key_id] = _out


# Generate default colors (all blue)
DEFAULT_COLORS = {(r, c): (25, 0, 255) for r in range(6) for c in range(21)}


__all__ = [
    "DEFAULT_LAYOUT_TWEAKS",
    "DEFAULT_KEYMAP",
    "DEFAULT_PER_KEY_TWEAKS",
    "DEFAULT_COLORS",
]
