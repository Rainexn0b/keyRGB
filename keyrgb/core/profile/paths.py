from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from keyrgb.core.config import Config
from keyrgb.core.utils.logging_utils import log_throttled

from .json_storage import read_json_strict, write_json_atomic

DEFAULT_PROFILE_NAME = "default"
_RESERVED_PROFILE_NAMES = frozenset({".", ".."})

# Older profile names that still resolve to the current built-ins.
_PROFILE_NAME_ALIASES = {
    "light": DEFAULT_PROFILE_NAME,
}

# Built-in profiles are always shown in the per-key editor, even if the user has
# not created them yet.
BUILTIN_PROFILE_NAMES = (DEFAULT_PROFILE_NAME,)


logger = logging.getLogger(__name__)


class ProfilePathError(ValueError):
    """Raised when a profile directory would escape its storage root."""


def _resolve_profile_file_path(*, root: Path, new_name: str, old_name: str) -> Path:
    """Return the preferred path and rename older filenames when safe.

    If the new path already exists, it wins.
    If only the older path exists, we attempt to rename it to the new path.
    On failure, fall back to the older path.
    """

    new_path = root / new_name
    old_path = root / old_name

    if new_path.exists() or not old_path.exists():
        return new_path

    try:
        old_path.rename(new_path)
        return new_path
    except OSError as exc:
        log_throttled(
            logger,
            "profile_paths.rename_previous_file",
            interval_s=60,
            level=logging.DEBUG,
            msg=f"Failed to rename older profile file {old_path.name} -> {new_path.name}",
            exc=exc,
        )
        return old_path


def safe_profile_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return DEFAULT_PROFILE_NAME
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    name = name or DEFAULT_PROFILE_NAME
    if name in _RESERVED_PROFILE_NAMES:
        return DEFAULT_PROFILE_NAME
    return _PROFILE_NAME_ALIASES.get(name, name)


def profiles_root() -> Path:
    return Config.CONFIG_DIR / "profiles"


def _validate_profile_root(candidate: Path, *, profile_name: str) -> Path:
    """Validate that one candidate is a non-symlink child of profile storage."""

    root_dir = profiles_root()

    try:
        resolved_root = root_dir.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ProfilePathError(f"Could not validate profile path '{profile_name}'") from exc

    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(resolved_root):
        raise ProfilePathError(f"Profile path '{profile_name}' resolves outside the profiles root")
    if candidate.is_symlink():
        raise ProfilePathError(f"Profile path '{profile_name}' must not be a directory symlink")
    return candidate


def _profile_root_path(name: str) -> Path:
    """Return one validated direct child of the profile storage root.

    Profile names are normalized for compatibility, then the filesystem-resolved
    path is checked as a defense in depth against existing directory symlinks.
    Individual profile-directory symlinks are not supported.
    """

    safe_name = safe_profile_name(name)
    return _validate_profile_root(profiles_root() / safe_name, profile_name=safe_name)


def active_profile_path() -> Path:
    return Config.CONFIG_DIR / "active_profile.json"


def default_profile_path() -> Path:
    return Config.CONFIG_DIR / "default_profile.json"


def get_default_profile() -> str:
    """Return the configured default profile name.

    Used as a fallback when no last active profile is remembered.
    """

    p = default_profile_path()
    try:
        raw = read_json_strict(p)
        if isinstance(raw, dict) and isinstance(raw.get("name"), str):
            return safe_profile_name(raw["name"])
    except FileNotFoundError:
        pass
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        log_throttled(
            logger,
            "profile_paths.get_default_profile",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to read default profile; using built-in default",
            exc=exc,
        )
    return DEFAULT_PROFILE_NAME


def set_default_profile(name: str) -> str:
    name = safe_profile_name(name)
    ensure_profile(name)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(default_profile_path(), {"name": name}, sort_keys=False)
    return name


def get_active_profile() -> str:
    p = active_profile_path()
    try:
        raw = read_json_strict(p)
        if isinstance(raw, dict) and isinstance(raw.get("name"), str):
            return safe_profile_name(raw["name"])
    except FileNotFoundError:
        pass
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Best-effort: fall back to default and log only occasionally.
        log_throttled(
            logger,
            "profile_paths.get_active_profile",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to read active profile; using default",
            exc=exc,
        )
    # If we don't have a remembered last active profile, fall back to a
    # user-chosen default profile if configured.
    return get_default_profile()


def ensure_profile(name: str) -> Path:
    name = safe_profile_name(name)
    new_root = _profile_root_path(name)

    # Rename older built-in directory names to the current name when safe.
    previous_name = None
    for old, new in _PROFILE_NAME_ALIASES.items():
        if new == name:
            previous_name = old
            break
    if previous_name is not None and not new_root.exists():
        old_root = _validate_profile_root(profiles_root() / previous_name, profile_name=previous_name)
        if old_root.exists():
            try:
                old_root.rename(new_root)
            except OSError as exc:
                log_throttled(
                    logger,
                    "profile_paths.rename_previous_dir",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg=f"Failed to rename older profile directory {old_root.name} -> {new_root.name}",
                    exc=exc,
                )
                root = old_root
            else:
                root = new_root
        else:
            root = new_root
    else:
        root = new_root

    root.mkdir(parents=True, exist_ok=True)
    # Validate again after migration/creation so an existing or migrated
    # directory symlink can never become a profile storage root.
    _validate_profile_root(root, profile_name=name)
    return root


def set_active_profile(name: str) -> str:
    name = safe_profile_name(name)
    ensure_profile(name)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(active_profile_path(), {"name": name}, sort_keys=False)
    return name


def list_profiles() -> list[str]:
    root = profiles_root()
    if not root.exists():
        return list(BUILTIN_PROFILE_NAMES)

    out: list[str] = []
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            out.append(child.name)

    # Stable ordering: built-ins first, then any custom profiles sorted.
    custom = sorted({n for n in out if n not in BUILTIN_PROFILE_NAMES})
    return list(BUILTIN_PROFILE_NAMES) + custom


def delete_profile(name: str) -> bool:
    name = safe_profile_name(name)
    if name in BUILTIN_PROFILE_NAMES:
        return False
    try:
        root = _profile_root_path(name)
    except ProfilePathError as exc:
        logger.warning("Refusing to delete unsafe profile path '%s': %s", name, exc)
        return False
    if not root.is_dir():
        return False
    shutil.rmtree(root)
    return True


@dataclass(frozen=True)
class ProfilePaths:
    root: Path
    keymap: Path
    layout_global: Path
    layout_per_key: Path
    layout_slots: Path
    lightbar_overlay: Path
    per_key_colors: Path
    backdrop_image: Path
    backdrop_settings: Path
    secondary_lighting: Path


def paths_for(name: str | None = None) -> ProfilePaths:
    if not name:
        name = get_active_profile()
    name = safe_profile_name(name)
    root = ensure_profile(name)

    # Current device-agnostic filenames.
    # Older Y15 Pro-named files are still renamed in place when safe.
    keymap = _resolve_profile_file_path(root=root, new_name="keymap.json", old_name="keymap_y15_pro.json")
    layout_global = _resolve_profile_file_path(
        root=root,
        new_name="layout_tweaks.json",
        old_name="layout_tweaks_y15_pro.json",
    )
    layout_per_key = _resolve_profile_file_path(
        root=root,
        new_name="layout_tweaks_per_key.json",
        old_name="layout_tweaks_y15_pro_perkey.json",
    )
    backdrop_image = _resolve_profile_file_path(root=root, new_name="backdrop.png", old_name="backdrop_y15_pro.png")
    backdrop_settings = _resolve_profile_file_path(
        root=root,
        new_name="backdrop_settings.json",
        old_name="backdrop_settings_y15_pro.json",
    )

    return ProfilePaths(
        root=root,
        keymap=keymap,
        layout_global=layout_global,
        layout_per_key=layout_per_key,
        layout_slots=root / "layout_slots.json",
        lightbar_overlay=root / "lightbar_overlay.json",
        per_key_colors=root / "per_key_colors.json",
        backdrop_image=backdrop_image,
        backdrop_settings=backdrop_settings,
        secondary_lighting=root / "secondary_lighting.json",
    )
