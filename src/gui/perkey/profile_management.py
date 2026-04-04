from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Tuple

from src.core.profile import profiles
from src.core.config import Config
from src.core.resources.layouts import key_id_for_slot_id, slot_id_for_key_id


PerKeyColors = Dict[Tuple[int, int], Tuple[int, int, int]]
KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]
Keymap = Dict[str, KeyCells]


def _candidate_keymap_identities(
    *,
    key_id: str | None,
    slot_id: str | None,
    physical_layout: str | None,
) -> tuple[str, ...]:
    out: list[str] = []

    def _add(identity: str | None) -> None:
        normalized = str(identity or "").strip()
        if normalized and normalized not in out:
            out.append(normalized)

    _add(slot_id)
    _add(key_id)

    if physical_layout:
        if key_id:
            _add(slot_id_for_key_id(physical_layout, key_id))
        if slot_id:
            _add(key_id_for_slot_id(physical_layout, slot_id))

    return tuple(out)


def _is_valid_cell(cell: Tuple[int, int], *, num_rows: int, num_cols: int) -> bool:
    row, col = int(cell[0]), int(cell[1])
    return 0 <= row < int(num_rows) and 0 <= col < int(num_cols)


def _coerce_cell(raw: object) -> KeyCell | None:
    if isinstance(raw, str) and "," in raw:
        row_text, col_text = raw.split(",", 1)
        try:
            return (int(row_text), int(col_text))
        except (TypeError, ValueError):
            return None

    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        first, second = raw
        if isinstance(first, (list, tuple, dict)) or isinstance(second, (list, tuple, dict)):
            return None
        try:
            return (int(first), int(second))
        except (TypeError, ValueError):
            return None

    return None


def _coerce_cells(raw: object) -> KeyCells:
    single = _coerce_cell(raw)
    if single is not None:
        return (single,)

    if not isinstance(raw, (list, tuple)):
        return ()

    out: list[KeyCell] = []
    seen: set[KeyCell] = set()
    for item in raw:
        cell = _coerce_cell(item)
        if cell is None or cell in seen:
            continue
        seen.add(cell)
        out.append(cell)
    return tuple(out)


def sanitize_keymap_cells(
    keymap: Mapping[str, object],
    *,
    num_rows: int,
    num_cols: int,
) -> Keymap:
    out: Keymap = {}
    for key_id, raw_cells in (keymap or {}).items():
        valid_cells: list[KeyCell] = []
        for cell in _coerce_cells(raw_cells):
            if _is_valid_cell(cell, num_rows=num_rows, num_cols=num_cols):
                valid_cells.append((int(cell[0]), int(cell[1])))
        if valid_cells:
            out[str(key_id)] = tuple(valid_cells)
    return out


def keymap_cells_for(
    keymap: Mapping[str, object],
    key_id: str | None,
    *,
    slot_id: str | None = None,
    physical_layout: str | None = None,
) -> KeyCells:
    for identity in _candidate_keymap_identities(key_id=key_id, slot_id=slot_id, physical_layout=physical_layout):
        cells = _coerce_cells((keymap or {}).get(identity))
        if cells:
            return cells
    return ()


def primary_cell(cells: object) -> KeyCell | None:
    normalized = _coerce_cells(cells)
    if not normalized:
        return None
    return normalized[0]


def representative_cell(cells: object, colors: Mapping[KeyCell, object] | None = None) -> KeyCell | None:
    normalized = _coerce_cells(cells)
    if not normalized:
        return None
    if colors:
        for cell in normalized:
            if cell in colors:
                return cell
    return normalized[0]


def primary_cell_for_key(
    keymap: Mapping[str, object],
    key_id: str | None,
    *,
    slot_id: str | None = None,
    physical_layout: str | None = None,
) -> KeyCell | None:
    return primary_cell(keymap_cells_for(keymap, key_id, slot_id=slot_id, physical_layout=physical_layout))


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
    except (TypeError, ValueError):
        cfg_colors = {}

    if cfg_colors:
        return sanitize_color_map_cells(cfg_colors, num_rows=num_rows, num_cols=num_cols)

    return sanitize_color_map_cells(dict(current_colors or {}), num_rows=num_rows, num_cols=num_cols)


@dataclass(frozen=True)
class ActivatedProfile:
    name: str
    keymap: Keymap
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
    per_key_layout_tweaks = profiles.normalize_layout_per_key_tweaks(
        profiles.load_layout_per_key(name, physical_layout=physical_layout),
        physical_layout=physical_layout,
    )
    layout_slot_overrides = profiles.normalize_layout_slot_overrides(
        profiles.load_layout_slots(name, physical_layout=physical_layout),
        physical_layout=physical_layout,
    )
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
    keymap: Keymap,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    lightbar_overlay: Dict[str, bool | float] | None = None,
    physical_layout: str,
    layout_slot_overrides: Dict[str, Dict[str, object]] | None = None,
    colors: PerKeyColors,
) -> str:
    name = profiles.set_active_profile(requested_name)

    profiles.save_keymap(keymap, name, physical_layout=physical_layout)
    profiles.save_layout_global(layout_tweaks, name)
    profiles.save_layout_per_key(
        profiles.normalize_layout_per_key_tweaks(per_key_layout_tweaks, physical_layout=physical_layout),
        name,
    )
    profiles.save_lightbar_overlay(dict(lightbar_overlay or {}), name)
    profiles.save_layout_slots(
        profiles.normalize_layout_slot_overrides(layout_slot_overrides or {}, physical_layout=physical_layout),
        name,
        physical_layout=physical_layout,
    )
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

    safe = profiles.safe_profile_name(name)
    if profiles.get_active_profile() == safe:
        profiles.set_active_profile(profiles.DEFAULT_PROFILE_NAME)

    return DeleteProfileResult(
        deleted=True,
        active_profile=profiles.get_active_profile(),
        message=f"Deleted lighting profile: {safe}",
    )
