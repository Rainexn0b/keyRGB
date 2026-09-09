"""Tk-free advisory locks ensuring one live process per GUI window identity."""

from __future__ import annotations

import atexit
import logging
import os
import re
from pathlib import Path
from typing import IO

from keyrgb.core.config.paths import config_dir

logger = logging.getLogger(__name__)

__all__ = [
    "acquire_gui_instance_lock",
    "acquire_gui_instance_or_exit",
    "gui_instance_lock_path",
    "release_all_gui_instance_locks",
    "release_gui_instance_lock",
]

_STATIC_IDENTITIES = frozenset(
    {
        "settings",
        "reactive-color",
        "power-mode",
        "support",
        "perkey",
        "calibrator",
    }
)

_UNIFORM_IDENTITY_RE = re.compile(r"uniform-[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_gui_lock_fhs: dict[str, IO[str]] = {}
_atexit_registered = False


def _normalize_identity(identity: str) -> str:
    if not isinstance(identity, str):
        raise ValueError(f"invalid GUI instance identity: {identity!r}")  # noqa: TRY004 - contract requires ValueError
    normalized = identity.lower()
    if normalized not in _STATIC_IDENTITIES and _UNIFORM_IDENTITY_RE.fullmatch(normalized) is None:
        raise ValueError(f"invalid GUI instance identity: {identity!r}")
    return normalized


def gui_instance_lock_path(identity: str) -> Path:
    """Return the advisory lock path for a GUI window identity."""
    normalized = _normalize_identity(identity)
    return config_dir() / f"keyrgb-gui-{normalized}.lock"


def acquire_gui_instance_lock(identity: str) -> bool:
    """Acquire the non-blocking advisory lock for a GUI window identity.

    Returns True when this process owns the identity (including reentrant
    same-process acquires) and False when another live process holds it.
    Unexpected programming errors (invalid identity) raise ValueError.
    """

    normalized = _normalize_identity(identity)
    if normalized in _gui_lock_fhs:
        return True

    try:
        import fcntl
    except ImportError:
        return True

    lock_path = gui_instance_lock_path(normalized)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fh = lock_path.open("a+", encoding="utf-8")
    except OSError:
        return False
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fh.close()
        return False

    try:
        lock_fh.seek(0)
        lock_fh.truncate()
        lock_fh.write(f"pid={os.getpid()} identity={normalized}\n")
        lock_fh.flush()
    except OSError:
        lock_fh.close()
        return False
    _gui_lock_fhs[normalized] = lock_fh
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(release_all_gui_instance_locks)
        _atexit_registered = True
    return True


def release_gui_instance_lock(identity: str) -> None:
    """Release this process's advisory lock for a GUI window identity, if held."""

    normalized = _normalize_identity(identity)
    lock_fh = _gui_lock_fhs.pop(normalized, None)
    if lock_fh is not None:
        lock_fh.close()


def release_all_gui_instance_locks() -> None:
    """Release every GUI instance advisory lock held by this process."""

    lock_fhs = list(_gui_lock_fhs.values())
    _gui_lock_fhs.clear()
    for lock_fh in lock_fhs:
        lock_fh.close()


def acquire_gui_instance_or_exit(identity: str) -> None:
    """Acquire a GUI instance lock or exit quietly when a duplicate runs."""

    normalized = _normalize_identity(identity)
    if acquire_gui_instance_lock(normalized):
        return
    lock_path = gui_instance_lock_path(normalized)
    logger.warning("GUI instance %r already running (%s); exiting", normalized, lock_path)
    raise SystemExit(0)
