"""Profile storage for per-key tools.

Profiles are *local* (per-user) and stored under:
  ~/.config/keyrgb/profiles/<profile_name>/

A profile groups:
- Keymap (visual key_id -> matrix row,col)
- Overlay alignment tweaks (global + per-key overrides)
- Per-key colors

The tray app still applies lighting from `config.json`. Per-key tools load/apply
profile data by writing to config when you activate a profile.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .json_storage import read_json, write_json_atomic
from .paths import (
    DEFAULT_PROFILE_NAME,
    ProfilePaths,
    delete_profile,
    get_active_profile,
    list_profiles,
    paths_for,
    set_active_profile,
)
from src.core.resources.defaults import (
    DEFAULT_COLORS,
    DEFAULT_KEYMAP,
    DEFAULT_LAYOUT_TWEAKS,
    DEFAULT_PER_KEY_TWEAKS,
)

# Backwards-compatible constant
_DEFAULT_PROFILE = DEFAULT_PROFILE_NAME


def load_keymap(name: str | None = None) -> Dict[str, Tuple[int, int]]:
    p = paths_for(name).keymap
    raw = read_json(p)
    if raw is None:
        raw = DEFAULT_KEYMAP

    out: Dict[str, Tuple[int, int]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and "," in v:
                a, b = v.split(",", 1)
                try:
                    out[k] = (int(a), int(b))
                except Exception:
                    continue
            elif isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 2:
                try:
                    out[k] = (int(v[0]), int(v[1]))
                except Exception:
                    continue
    return out


def save_keymap(keymap: Dict[str, Tuple[int, int]], name: str | None = None) -> None:
    p = paths_for(name).keymap
    payload = {k: f"{rc[0]},{rc[1]}" for k, rc in sorted(keymap.items())}
    write_json_atomic(p, payload)


def load_layout_global(name: str | None = None) -> Dict[str, float]:
    p = paths_for(name).layout_global
    raw = read_json(p)
    if raw is None:
        raw = DEFAULT_LAYOUT_TWEAKS

    out = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    if isinstance(raw, dict):
        for k in list(out.keys()):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                out[k] = float(v)
    out["inset"] = max(0.0, min(0.20, float(out.get("inset", 0.06))))
    return out


def save_layout_global(tweaks: Dict[str, float], name: str | None = None) -> None:
    p = paths_for(name).layout_global
    payload = {
        "dx": float(tweaks.get("dx", 0.0)),
        "dy": float(tweaks.get("dy", 0.0)),
        "sx": float(tweaks.get("sx", 1.0)),
        "sy": float(tweaks.get("sy", 1.0)),
        "inset": float(tweaks.get("inset", 0.06)),
    }
    write_json_atomic(p, payload)


def load_layout_per_key(name: str | None = None) -> Dict[str, Dict[str, float]]:
    p = paths_for(name).layout_per_key
    raw = read_json(p)
    if raw is None:
        raw = DEFAULT_PER_KEY_TWEAKS

    out: Dict[str, Dict[str, float]] = {}
    if isinstance(raw, dict):
        for key_id, tweaks in raw.items():
            if not isinstance(key_id, str) or not isinstance(tweaks, dict):
                continue
            t: Dict[str, float] = {}
            for k in ("dx", "dy", "sx", "sy", "inset"):
                v = tweaks.get(k)
                if isinstance(v, (int, float)):
                    t[k] = float(v)
            if t:
                # Clamp inset if present
                if "inset" in t:
                    t["inset"] = max(0.0, min(0.20, float(t["inset"])))
                out[key_id] = t
    return out


def save_layout_per_key(per_key: Dict[str, Dict[str, float]], name: str | None = None) -> None:
    p = paths_for(name).layout_per_key
    payload: Dict[str, Dict[str, float]] = {}
    for key_id, tweaks in (per_key or {}).items():
        if not isinstance(key_id, str) or not isinstance(tweaks, dict):
            continue
        t: Dict[str, float] = {}
        for k in ("dx", "dy", "sx", "sy", "inset"):
            if k in tweaks and isinstance(tweaks[k], (int, float)):
                t[k] = float(tweaks[k])
        if t:
            if "inset" in t:
                t["inset"] = max(0.0, min(0.20, float(t["inset"])))
            payload[key_id] = t
    write_json_atomic(p, payload)


def load_per_key_colors(name: str | None = None) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    p = paths_for(name).per_key_colors
    raw = read_json(p)
    if raw is None:
        return DEFAULT_COLORS.copy()

    out: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            rs, cs = str(k).split(",", 1)
            r = int(rs.strip())
            c = int(cs.strip())
            rr, gg, bb = v
            out[(r, c)] = (int(rr), int(gg), int(bb))
        except Exception:
            continue
    return out


def save_per_key_colors(colors: Dict[Tuple[int, int], Tuple[int, int, int]], name: str | None = None) -> None:
    p = paths_for(name).per_key_colors
    payload: Dict[str, list[int]] = {}
    for (r, c), rgb in (colors or {}).items():
        try:
            rr, gg, bb = rgb
            payload[f"{int(r)},{int(c)}"] = [int(rr), int(gg), int(bb)]
        except Exception:
            continue
    write_json_atomic(p, payload)


def apply_profile_to_config(cfg, colors: Dict[Tuple[int, int], Tuple[int, int, int]]) -> None:
    # Ensure visible when activating a per-key profile.
    if getattr(cfg, "brightness", 0) <= 0:
        cfg.brightness = 50
    cfg.effect = "perkey"
    cfg.per_key_colors = colors
