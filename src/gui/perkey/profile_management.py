from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from src.core.profile import profiles
from src.core.config import Config


PerKeyColors = Dict[Tuple[int, int], Tuple[int, int, int]]


def load_profile_colors(*, name: str, config: Config, current_colors: PerKeyColors) -> PerKeyColors:
    """Load per-key colors for a profile with sensible fallbacks.

    Profiles may exist without a saved per-key map yet; in that case we should not
    replace the editor colors with an empty dict.
    """

    prof_colors = profiles.load_per_key_colors(name)
    if prof_colors:
        return dict(prof_colors)

    try:
        cfg_colors = dict(getattr(config, "per_key_colors", {}) or {})
    except Exception:
        cfg_colors = {}

    if cfg_colors:
        return cfg_colors

    return dict(current_colors or {})


@dataclass(frozen=True)
class ActivatedProfile:
    name: str
    keymap: Dict[str, Tuple[int, int]]
    layout_tweaks: Dict[str, float]
    per_key_layout_tweaks: Dict[str, Dict[str, float]]
    colors: PerKeyColors


def activate_profile(
    requested_name: str,
    *,
    config: Config,
    current_colors: PerKeyColors,
) -> ActivatedProfile:
    name = profiles.set_active_profile(requested_name)

    keymap = profiles.load_keymap(name)
    layout_tweaks = profiles.load_layout_global(name)
    per_key_layout_tweaks = profiles.load_layout_per_key(name)

    colors = load_profile_colors(name=name, config=config, current_colors=current_colors)
    profiles.apply_profile_to_config(config, colors)

    return ActivatedProfile(
        name=name,
        keymap=keymap,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        colors=colors,
    )


def save_profile(
    requested_name: str,
    *,
    config: Config,
    keymap: Dict[str, Tuple[int, int]],
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    colors: PerKeyColors,
) -> str:
    name = profiles.set_active_profile(requested_name)

    profiles.save_keymap(keymap, name)
    profiles.save_layout_global(layout_tweaks, name)
    profiles.save_layout_per_key(per_key_layout_tweaks, name)
    profiles.save_per_key_colors(colors, name)
    profiles.apply_profile_to_config(config, colors)

    return name


@dataclass(frozen=True)
class DeleteProfileResult:
    deleted: bool
    active_profile: str
    message: str


def delete_profile(requested_name: str) -> DeleteProfileResult:
    name = requested_name.strip()
    if not name:
        return DeleteProfileResult(deleted=False, active_profile=profiles.get_active_profile(), message="")

    if not profiles.delete_profile(name):
        return DeleteProfileResult(
            deleted=False,
            active_profile=profiles.get_active_profile(),
            message=f"Cannot delete '{profiles.DEFAULT_PROFILE_NAME}'",
        )

    safe = profiles._safe_name(name)
    if profiles.get_active_profile() == safe:
        profiles.set_active_profile(profiles.DEFAULT_PROFILE_NAME)

    return DeleteProfileResult(
        deleted=True,
        active_profile=profiles.get_active_profile(),
        message=f"Deleted profile: {safe}",
    )
