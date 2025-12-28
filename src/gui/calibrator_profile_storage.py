from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from src.core import profiles


def get_active_profile_name() -> str:
    return profiles.get_active_profile()


def keymap_path(profile_name: str) -> Path:
    return profiles.paths_for(profile_name).keymap


def load_keymap(profile_name: str) -> Dict[str, Tuple[int, int]]:
    return profiles.load_keymap(profile_name)


def save_keymap(profile_name: str, keymap: Dict[str, Tuple[int, int]]) -> None:
    profiles.save_keymap(keymap, profile_name)


def load_layout_global(profile_name: str) -> Dict[str, float]:
    return profiles.load_layout_global(profile_name)


def load_layout_per_key(profile_name: str) -> Dict[str, Dict[str, float]]:
    return profiles.load_layout_per_key(profile_name)
