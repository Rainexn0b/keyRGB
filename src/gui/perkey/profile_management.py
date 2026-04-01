from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.core.profile import profiles
from src.core.config import Config


PerKeyColors = Dict[Tuple[int, int], Tuple[int, int, int]]


def _is_valid_cell(cell: Tuple[int, int], *, num_rows: int, num_cols: int) -> bool:
    row, col = int(cell[0]), int(cell[1])
    return 0 <= row < int(num_rows) and 0 <= col < int(num_cols)


def sanitize_keymap_cells(
    keymap: Dict[str, Tuple[int, int]],
    *,
    num_rows: int,
    num_cols: int,
) -> Dict[str, Tuple[int, int]]:
    return {
        str(key_id): (int(cell[0]), int(cell[1]))
        for key_id, cell in (keymap or {}).items()
        if _is_valid_cell(cell, num_rows=num_rows, num_cols=num_cols)
    }


def sanitize_color_map_cells(
    color_map: PerKeyColors,
    *,
    num_rows: int,
    num_cols: int,
) -> PerKeyColors:
    return {
        (int(cell[0]), int(cell[1])): (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        for cell, rgb in (color_map or {}).items()
        if _is_valid_cell(cell, num_rows=num_rows, num_cols=num_cols)
    }


def load_profile_colors(
    *,
    name: str,
    config: Config,
    current_colors: PerKeyColors,
    num_rows: int,
    num_cols: int,
) -> PerKeyColors:
    """Load per-key colors for a profile with sensible fallbacks.

    Profiles may exist without a saved per-key map yet; in that case we should not
    replace the editor colors with an empty dict.
    """

    prof_colors = profiles.load_per_key_colors(name)
    if prof_colors:
        return sanitize_color_map_cells(prof_colors, num_rows=num_rows, num_cols=num_cols)

    try:
        cfg_colors = dict(getattr(config, "per_key_colors", {}) or {})
    except Exception:
        cfg_colors = {}

    if cfg_colors:
        return sanitize_color_map_cells(cfg_colors, num_rows=num_rows, num_cols=num_cols)

    return sanitize_color_map_cells(dict(current_colors or {}), num_rows=num_rows, num_cols=num_cols)


@dataclass(frozen=True)
class ActivatedProfile:
    name: str
    keymap: Dict[str, Tuple[int, int]]
    layout_tweaks: Dict[str, float]
    per_key_layout_tweaks: Dict[str, Dict[str, float]]
    colors: PerKeyColors
    layout_slot_overrides: Dict[str, Dict[str, object]] = field(default_factory=dict)
    lightbar_overlay: Dict[str, bool | float] = field(default_factory=dict)


def activate_profile(
    requested_name: str,
    *,
    config: Config,
    current_colors: PerKeyColors,
    num_rows: int,
    num_cols: int,
    physical_layout: str,
) -> ActivatedProfile:
    name = profiles.set_active_profile(requested_name)

    keymap = sanitize_keymap_cells(
        profiles.load_keymap(name, physical_layout=physical_layout),
        num_rows=num_rows,
        num_cols=num_cols,
    )
    layout_tweaks = profiles.load_layout_global(name, physical_layout=physical_layout)
    per_key_layout_tweaks = profiles.load_layout_per_key(name, physical_layout=physical_layout)
    layout_slot_overrides = profiles.load_layout_slots(name, physical_layout=physical_layout)
    lightbar_overlay = profiles.load_lightbar_overlay(name)

    colors = load_profile_colors(
        name=name,
        config=config,
        current_colors=current_colors,
        num_rows=num_rows,
        num_cols=num_cols,
    )
    profiles.apply_profile_to_config(config, colors)

    return ActivatedProfile(
        name=name,
        keymap=keymap,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        colors=colors,
        layout_slot_overrides=layout_slot_overrides,
        lightbar_overlay=lightbar_overlay,
    )


def save_profile(
    requested_name: str,
    *,
    config: Config,
    keymap: Dict[str, Tuple[int, int]],
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    lightbar_overlay: Dict[str, bool | float] | None = None,
    physical_layout: str,
    layout_slot_overrides: Dict[str, Dict[str, object]] | None = None,
    colors: PerKeyColors,
) -> str:
    name = profiles.set_active_profile(requested_name)

    profiles.save_keymap(keymap, name)
    profiles.save_layout_global(layout_tweaks, name)
    profiles.save_layout_per_key(per_key_layout_tweaks, name)
    profiles.save_lightbar_overlay(dict(lightbar_overlay or {}), name)
    profiles.save_layout_slots(dict(layout_slot_overrides or {}), name, physical_layout=physical_layout)
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
            message=f"Cannot delete lighting profile '{profiles.DEFAULT_PROFILE_NAME}'",
        )

    safe = profiles._safe_name(name)
    if profiles.get_active_profile() == safe:
        profiles.set_active_profile(profiles.DEFAULT_PROFILE_NAME)

    return DeleteProfileResult(
        deleted=True,
        active_profile=profiles.get_active_profile(),
        message=f"Deleted lighting profile: {safe}",
    )
