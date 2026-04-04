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

import logging
from src.core.config import layout_slots as config_layout_slots
from src.core.resources import defaults as resource_defaults
from src.core.resources import layout_slots as resource_layout_slots
from src.core.resources import layouts as resource_layouts
from src.core.utils import logging_utils

from . import _backdrop as backdrop_ops
from . import _profile_apply_ops as apply_ops
from . import _profile_storage_ops as storage_ops
from . import json_storage
from . import paths as profile_paths


load_backdrop_mode = backdrop_ops.load_backdrop_mode
load_backdrop_transparency = backdrop_ops.load_backdrop_transparency
normalize_backdrop_mode = backdrop_ops.normalize_backdrop_mode
save_backdrop_mode = backdrop_ops.save_backdrop_mode
save_backdrop_transparency = backdrop_ops.save_backdrop_transparency

read_json = json_storage.read_json
write_json_atomic = json_storage.write_json_atomic

default_profile_path = profile_paths.default_profile_path
DEFAULT_PROFILE_NAME = profile_paths.DEFAULT_PROFILE_NAME
delete_profile = profile_paths.delete_profile
get_default_profile = profile_paths.get_default_profile
get_active_profile = profile_paths.get_active_profile
list_profiles = profile_paths.list_profiles
paths_for = profile_paths.paths_for
profiles_root = profile_paths.profiles_root
safe_profile_name = profile_paths.safe_profile_name
set_active_profile = profile_paths.set_active_profile
set_default_profile = profile_paths.set_default_profile

load_layout_slot_overrides = config_layout_slots.load_layout_slot_overrides
save_layout_slot_overrides = config_layout_slots.save_layout_slot_overrides

DEFAULT_COLORS = resource_defaults.DEFAULT_COLORS
get_default_lightbar_overlay = resource_defaults.get_default_lightbar_overlay
get_default_keymap = resource_defaults.get_default_keymap
get_default_layout_tweaks = resource_defaults.get_default_layout_tweaks
get_default_per_key_tweaks = resource_defaults.get_default_per_key_tweaks

key_id_for_slot_id = resource_layouts.key_id_for_slot_id
slot_id_for_key_id = resource_layouts.slot_id_for_key_id
sanitize_layout_slot_overrides = resource_layout_slots.sanitize_layout_slot_overrides
log_throttled = logging_utils.log_throttled

# Backwards-compatible constant
_DEFAULT_PROFILE = DEFAULT_PROFILE_NAME
logger = logging.getLogger(__name__)

KeyCell = tuple[int, int]
KeyCells = tuple[KeyCell, ...]


__all__ = [
    "DEFAULT_PROFILE_NAME",
    "_DEFAULT_PROFILE",
    "default_profile_path",
    "apply_profile_to_config",
    "delete_profile",
    "get_default_profile",
    "get_active_profile",
    "list_profiles",
    "load_backdrop_mode",
    "load_backdrop_transparency",
    "load_keymap",
    "load_layout_global",
    "load_layout_per_key",
    "load_layout_slots",
    "load_lightbar_overlay",
    "load_per_key_colors",
    "normalize_backdrop_mode",
    "normalize_keymap",
    "normalize_layout_per_key_tweaks",
    "normalize_layout_slot_overrides",
    "paths_for",
    "profiles_root",
    "safe_profile_name",
    "save_backdrop_mode",
    "save_backdrop_transparency",
    "save_keymap",
    "save_layout_global",
    "save_layout_per_key",
    "save_layout_slots",
    "save_lightbar_overlay",
    "save_per_key_colors",
    "migrate_builtin_profile_brightness",
    "set_active_profile",
    "set_default_profile",
]


def _normalize_lightbar_overlay(raw: object) -> dict[str, bool | float]:
    return storage_ops.normalize_lightbar_overlay(
        raw,
        get_default_lightbar_overlay=get_default_lightbar_overlay,
    )


def _canonical_layout_identity(*, physical_layout: str | None, identity: object) -> str:
    return storage_ops.canonical_layout_identity(
        physical_layout=physical_layout,
        identity=identity,
        slot_id_for_key_id=slot_id_for_key_id,
        key_id_for_slot_id=key_id_for_slot_id,
    )


def normalize_layout_per_key_tweaks(
    raw: object,
    *,
    physical_layout: str | None,
) -> dict[str, dict[str, float]]:
    return storage_ops.normalize_layout_per_key_tweaks(
        raw,
        physical_layout=physical_layout,
        canonical_layout_identity_fn=_canonical_layout_identity,
    )


def normalize_layout_slot_overrides(
    raw: object,
    *,
    physical_layout: str | None,
) -> dict[str, dict[str, object]]:
    return storage_ops.normalize_layout_slot_overrides(
        raw,
        physical_layout=physical_layout,
        sanitize_layout_slot_overrides=sanitize_layout_slot_overrides,
    )


def normalize_keymap(
    raw: object,
    *,
    physical_layout: str | None,
) -> dict[str, KeyCells]:
    return storage_ops.normalize_keymap(
        raw,
        physical_layout=physical_layout,
        canonical_layout_identity_fn=_canonical_layout_identity,
    )


def load_keymap(name: str | None = None, *, physical_layout: str | None = None) -> dict[str, KeyCells]:
    return storage_ops.load_keymap(
        name=name,
        physical_layout=physical_layout,
        paths_for=paths_for,
        read_json=read_json,
        get_default_keymap=get_default_keymap,
        normalize_keymap_fn=normalize_keymap,
    )


def save_keymap(
    keymap: dict[str, KeyCells],
    name: str | None = None,
    *,
    physical_layout: str | None = None,
) -> None:
    storage_ops.save_keymap(
        keymap=keymap,
        name=name,
        physical_layout=physical_layout,
        paths_for=paths_for,
        write_json_atomic=write_json_atomic,
        normalize_keymap_fn=normalize_keymap,
    )


def load_layout_global(name: str | None = None, *, physical_layout: str | None = None) -> dict[str, float]:
    return storage_ops.load_layout_global(
        name=name,
        physical_layout=physical_layout,
        paths_for=paths_for,
        read_json=read_json,
        get_default_layout_tweaks=get_default_layout_tweaks,
    )


def save_layout_global(tweaks: dict[str, float], name: str | None = None) -> None:
    storage_ops.save_layout_global(tweaks=tweaks, name=name, paths_for=paths_for, write_json_atomic=write_json_atomic)


def load_layout_per_key(name: str | None = None, *, physical_layout: str | None = None) -> dict[str, dict[str, float]]:
    return storage_ops.load_layout_per_key(
        name=name,
        physical_layout=physical_layout,
        paths_for=paths_for,
        read_json=read_json,
        get_default_per_key_tweaks=get_default_per_key_tweaks,
        normalize_layout_per_key_tweaks_fn=normalize_layout_per_key_tweaks,
    )


def save_layout_per_key(per_key: dict[str, dict[str, float]], name: str | None = None) -> None:
    storage_ops.save_layout_per_key(
        per_key=per_key,
        name=name,
        paths_for=paths_for,
        write_json_atomic=write_json_atomic,
        normalize_layout_per_key_tweaks_fn=normalize_layout_per_key_tweaks,
    )


def load_lightbar_overlay(name: str | None = None) -> dict[str, bool | float]:
    return storage_ops.load_lightbar_overlay(
        name=name,
        paths_for=paths_for,
        read_json=read_json,
        get_default_lightbar_overlay=get_default_lightbar_overlay,
        normalize_lightbar_overlay_fn=_normalize_lightbar_overlay,
    )


def save_lightbar_overlay(
    overlay: dict[str, bool | float],
    name: str | None = None,
) -> dict[str, bool | float]:
    return storage_ops.save_lightbar_overlay(
        overlay=overlay,
        name=name,
        paths_for=paths_for,
        write_json_atomic=write_json_atomic,
        normalize_lightbar_overlay_fn=_normalize_lightbar_overlay,
    )


def load_layout_slots(
    name: str | None = None,
    *,
    physical_layout: str | None = None,
) -> dict[str, dict[str, object]]:
    return storage_ops.load_layout_slots(
        name=name,
        physical_layout=physical_layout,
        load_layout_slot_overrides=load_layout_slot_overrides,
        normalize_layout_slot_overrides_fn=normalize_layout_slot_overrides,
    )


def save_layout_slots(
    layout_slots: dict[str, dict[str, object]],
    name: str | None = None,
    *,
    physical_layout: str | None = None,
) -> dict[str, dict[str, object]]:
    return storage_ops.save_layout_slots(
        layout_slots=layout_slots,
        name=name,
        physical_layout=physical_layout,
        save_layout_slot_overrides=save_layout_slot_overrides,
        normalize_layout_slot_overrides_fn=normalize_layout_slot_overrides,
    )


def load_per_key_colors(
    name: str | None = None,
) -> dict[tuple[int, int], tuple[int, int, int]]:
    return storage_ops.load_per_key_colors(
        name=name,
        paths_for=paths_for,
        read_json=read_json,
        safe_profile_name=safe_profile_name,
        default_colors=DEFAULT_COLORS,
    )


def save_per_key_colors(colors: dict[tuple[int, int], tuple[int, int, int]], name: str | None = None) -> None:
    storage_ops.save_per_key_colors(
        colors=colors,
        name=name,
        paths_for=paths_for,
        write_json_atomic=write_json_atomic,
    )


def migrate_builtin_profile_brightness(cfg) -> bool:
    return apply_ops.migrate_builtin_profile_brightness(
        cfg,
        safe_profile_name=safe_profile_name,
        get_active_profile=get_active_profile,
        log_throttled=log_throttled,
        logger=logger,
    )


def apply_profile_to_config(cfg, colors: dict[tuple[int, int], tuple[int, int, int]]) -> None:
    apply_ops.apply_profile_to_config(
        cfg,
        colors,
        safe_profile_name=safe_profile_name,
        get_active_profile=get_active_profile,
        log_throttled=log_throttled,
        logger=logger,
    )
