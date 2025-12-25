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

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple


# Keep imports lightweight: Config lives in the same project.
from .config_legacy import Config


_DEFAULT_PROFILE = "default"


def _safe_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return _DEFAULT_PROFILE
    # Replace whitespace with underscores and drop unsafe characters.
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    return name or _DEFAULT_PROFILE


def profiles_root() -> Path:
    return Config.CONFIG_DIR / "profiles"


def active_profile_path() -> Path:
    return Config.CONFIG_DIR / "active_profile.json"


def get_active_profile() -> str:
    p = active_profile_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("name"), str):
                return _safe_name(raw["name"])
        except Exception:
            pass
    return _DEFAULT_PROFILE


def set_active_profile(name: str) -> str:
    name = _safe_name(name)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    active_profile_path().write_text(json.dumps({"name": name}, indent=2), encoding="utf-8")
    ensure_profile(name)
    return name


def list_profiles() -> list[str]:
    root = profiles_root()
    if not root.exists():
        return [_DEFAULT_PROFILE]
    out: list[str] = []
    for child in root.iterdir():
        if child.is_dir():
            out.append(child.name)
    if _DEFAULT_PROFILE not in out:
        out.append(_DEFAULT_PROFILE)
    return sorted(set(out))


def ensure_profile(name: str) -> Path:
    name = _safe_name(name)
    root = profiles_root() / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def delete_profile(name: str) -> bool:
    name = _safe_name(name)
    if name == _DEFAULT_PROFILE:
        return False
    root = profiles_root() / name
    if not root.exists():
        return False
    shutil.rmtree(root)
    return True


@dataclass(frozen=True)
class ProfilePaths:
    root: Path
    keymap: Path
    layout_global: Path
    layout_per_key: Path
    per_key_colors: Path


def paths_for(name: str | None = None) -> ProfilePaths:
    if not name:
        name = get_active_profile()
    name = _safe_name(name)
    root = ensure_profile(name)
    return ProfilePaths(
        root=root,
        keymap=root / "keymap_y15_pro.json",
        layout_global=root / "layout_tweaks_y15_pro.json",
        layout_per_key=root / "layout_tweaks_y15_pro_perkey.json",
        per_key_colors=root / "per_key_colors.json",
    )


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_keymap(name: str | None = None) -> Dict[str, Tuple[int, int]]:
    p = paths_for(name).keymap
    raw = _read_json(p)
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
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: f"{rc[0]},{rc[1]}" for k, rc in sorted(keymap.items())}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def load_layout_global(name: str | None = None) -> Dict[str, float]:
    p = paths_for(name).layout_global
    raw = _read_json(p)
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
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dx": float(tweaks.get("dx", 0.0)),
        "dy": float(tweaks.get("dy", 0.0)),
        "sx": float(tweaks.get("sx", 1.0)),
        "sy": float(tweaks.get("sy", 1.0)),
        "inset": float(tweaks.get("inset", 0.06)),
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def load_layout_per_key(name: str | None = None) -> Dict[str, Dict[str, float]]:
    p = paths_for(name).layout_per_key
    raw = _read_json(p)
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
    p.parent.mkdir(parents=True, exist_ok=True)
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
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def load_per_key_colors(name: str | None = None) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    p = paths_for(name).per_key_colors
    raw = _read_json(p)
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
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, list[int]] = {}
    for (r, c), rgb in (colors or {}).items():
        try:
            rr, gg, bb = rgb
            payload[f"{int(r)},{int(c)}"] = [int(rr), int(gg), int(bb)]
        except Exception:
            continue
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def apply_profile_to_config(cfg: Config, colors: Dict[Tuple[int, int], Tuple[int, int, int]]) -> None:
    # Ensure visible when activating a per-key profile.
    if getattr(cfg, "brightness", 0) <= 0:
        cfg.brightness = 50
    cfg.effect = "perkey"
    cfg.per_key_colors = colors
