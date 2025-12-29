from __future__ import annotations

import logging
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.logging_utils import log_throttled
from src.legacy.config import Config


DEFAULT_PROFILE_NAME = "default"


logger = logging.getLogger(__name__)


def safe_profile_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return DEFAULT_PROFILE_NAME
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    return name or DEFAULT_PROFILE_NAME


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
                return safe_profile_name(raw["name"])
        except Exception as exc:
            # Best-effort: fall back to default and log only occasionally.
            log_throttled(
                logger,
                "profile_paths.get_active_profile",
                interval_s=60,
                level=logging.DEBUG,
                msg="Failed to read active profile; using default",
                exc=exc,
            )
    return DEFAULT_PROFILE_NAME


def ensure_profile(name: str) -> Path:
    name = safe_profile_name(name)
    root = profiles_root() / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def set_active_profile(name: str) -> str:
    name = safe_profile_name(name)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    active_profile_path().write_text(json.dumps({"name": name}, indent=2), encoding="utf-8")
    ensure_profile(name)
    return name


def list_profiles() -> list[str]:
    root = profiles_root()
    if not root.exists():
        return [DEFAULT_PROFILE_NAME]
    out: list[str] = []
    for child in root.iterdir():
        if child.is_dir():
            out.append(child.name)
    if DEFAULT_PROFILE_NAME not in out:
        out.append(DEFAULT_PROFILE_NAME)
    return sorted(set(out))


def delete_profile(name: str) -> bool:
    name = safe_profile_name(name)
    if name == DEFAULT_PROFILE_NAME:
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
    backdrop_image: Path


def paths_for(name: str | None = None) -> ProfilePaths:
    if not name:
        name = get_active_profile()
    name = safe_profile_name(name)
    root = ensure_profile(name)
    return ProfilePaths(
        root=root,
        keymap=root / "keymap_y15_pro.json",
        layout_global=root / "layout_tweaks_y15_pro.json",
        layout_per_key=root / "layout_tweaks_y15_pro_perkey.json",
        per_key_colors=root / "per_key_colors.json",
        backdrop_image=root / "backdrop_y15_pro.png",
    )
