from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from src.core.profile import profiles

KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]


def get_active_profile_name() -> str:
    return profiles.get_active_profile()


def keymap_path(profile_name: str) -> Path:
    return profiles.paths_for(profile_name).keymap


def load_keymap(profile_name: str, *, physical_layout: str | None = None) -> Dict[str, KeyCells]:
    return profiles.load_keymap(profile_name, physical_layout=physical_layout)


def save_keymap(
    profile_name: str,
    keymap: Dict[str, KeyCells],
    *,
    physical_layout: str | None = None,
) -> None:
    profiles.save_keymap(keymap, profile_name, physical_layout=physical_layout)


def load_layout_global(profile_name: str, *, physical_layout: str | None = None) -> Dict[str, float]:
    return profiles.load_layout_global(profile_name, physical_layout=physical_layout)


def load_layout_per_key(profile_name: str, *, physical_layout: str | None = None) -> Dict[str, Dict[str, float]]:
    return profiles.load_layout_per_key(profile_name, physical_layout=physical_layout)


def load_layout_slots(profile_name: str, physical_layout: str) -> Dict[str, Dict[str, object]]:
    return profiles.load_layout_slots(profile_name, physical_layout=physical_layout)
