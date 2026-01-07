from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.utils.logging_utils import log_throttled
from src.core.config import Config


DEFAULT_PROFILE_NAME = "light"

# Backward compatibility: historical profile name used by older versions.
_LEGACY_PROFILE_ALIASES = {
    "default": DEFAULT_PROFILE_NAME,
}

# Built-in profiles are always shown in the per-key editor, even if the user has
# not created them yet.
BUILTIN_PROFILE_NAMES = (DEFAULT_PROFILE_NAME, "dark", "dim")


logger = logging.getLogger(__name__)


def _migrate_profile_file(*, root: Path, new_name: str, old_name: str) -> Path:
    """Return the preferred path and migrate legacy names when safe.

    If the new path already exists, it wins.
    If only the legacy path exists, we attempt to rename it to the new path.
    On failure, fall back to the legacy path.
    """

    new_path = root / new_name
    old_path = root / old_name

    if new_path.exists() or not old_path.exists():
        return new_path

    try:
        old_path.rename(new_path)
        return new_path
    except Exception as exc:
        log_throttled(
            logger,
            "profile_paths.migrate_legacy_file",
            interval_s=60,
            level=logging.DEBUG,
            msg=f"Failed to migrate {old_path.name} -> {new_path.name}",
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
    return _LEGACY_PROFILE_ALIASES.get(name, name)


def profiles_root() -> Path:
    return Config.CONFIG_DIR / "profiles"


def active_profile_path() -> Path:
    return Config.CONFIG_DIR / "active_profile.json"


def default_profile_path() -> Path:
    return Config.CONFIG_DIR / "default_profile.json"


def get_default_profile() -> str:
    """Return the configured default profile name.

    Used as a fallback when no last active profile is remembered.
    """

    p = default_profile_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("name"), str):
                return safe_profile_name(raw["name"])
        except Exception as exc:
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
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    default_profile_path().write_text(json.dumps({"name": name}, indent=2), encoding="utf-8")
    ensure_profile(name)
    return name


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
    # If we don't have a remembered last active profile, fall back to a
    # user-chosen default profile if configured.
    return get_default_profile()


def ensure_profile(name: str) -> Path:
    name = safe_profile_name(name)
    root_dir = profiles_root()

    # Migrate legacy built-in directory name to the new name when safe.
    legacy = None
    for old, new in _LEGACY_PROFILE_ALIASES.items():
        if new == name:
            legacy = old
            break
    if legacy is not None:
        new_root = root_dir / name
        old_root = root_dir / legacy
        if not new_root.exists() and old_root.exists():
            try:
                old_root.rename(new_root)
            except Exception as exc:
                log_throttled(
                    logger,
                    "profile_paths.migrate_legacy_dir",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg=f"Failed to migrate {old_root.name} -> {new_root.name}",
                    exc=exc,
                )
                root = old_root
            else:
                root = new_root
        else:
            root = new_root
    else:
        root = root_dir / name

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
        return list(BUILTIN_PROFILE_NAMES)

    out: list[str] = []
    for child in root.iterdir():
        if child.is_dir():
            out.append(child.name)

    # Stable ordering: built-ins first, then any custom profiles sorted.
    custom = sorted({n for n in out if n not in BUILTIN_PROFILE_NAMES})
    return list(BUILTIN_PROFILE_NAMES) + custom


def delete_profile(name: str) -> bool:
    name = safe_profile_name(name)
    if name in BUILTIN_PROFILE_NAMES:
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
    backdrop_settings: Path


def paths_for(name: str | None = None) -> ProfilePaths:
    if not name:
        name = get_active_profile()
    name = safe_profile_name(name)
    root = ensure_profile(name)

    # New, device-agnostic filenames.
    # We also support legacy Y15 Pro-named files and migrate them in-place.
    keymap = _migrate_profile_file(root=root, new_name="keymap.json", old_name="keymap_y15_pro.json")
    layout_global = _migrate_profile_file(
        root=root,
        new_name="layout_tweaks.json",
        old_name="layout_tweaks_y15_pro.json",
    )
    layout_per_key = _migrate_profile_file(
        root=root,
        new_name="layout_tweaks_per_key.json",
        old_name="layout_tweaks_y15_pro_perkey.json",
    )
    backdrop_image = _migrate_profile_file(root=root, new_name="backdrop.png", old_name="backdrop_y15_pro.png")
    backdrop_settings = _migrate_profile_file(
        root=root,
        new_name="backdrop_settings.json",
        old_name="backdrop_settings_y15_pro.json",
    )

    return ProfilePaths(
        root=root,
        keymap=keymap,
        layout_global=layout_global,
        layout_per_key=layout_per_key,
        per_key_colors=root / "per_key_colors.json",
        backdrop_image=backdrop_image,
        backdrop_settings=backdrop_settings,
    )
