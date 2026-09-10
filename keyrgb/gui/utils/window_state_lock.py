"""Advisory file locking and paths for Tk-free UI-state persistence (UX-06).

Owns ``config_dir()/ui-state.json`` path resolution and the blocking
advisory lock on ``ui-state.lock`` so ``window_state.py`` stays small.
Locking degrades gracefully when ``fcntl`` is unavailable. Adds no behavior.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from keyrgb.core.config.paths import config_dir

logger = logging.getLogger(__name__)

_UI_STATE_FILENAME = "ui-state.json"
_UI_STATE_LOCK_FILENAME = "ui-state.lock"


def ui_state_path() -> Path:
    """Return the UI-state JSON path (``config_dir()/ui-state.json``)."""

    return config_dir() / _UI_STATE_FILENAME


def ui_state_lock_path() -> Path:
    """Return the UI-state advisory-lock path (distinct from the JSON file)."""

    return config_dir() / _UI_STATE_LOCK_FILENAME


def acquire_ui_state_lock(*, exclusive: bool) -> int | None:
    """Acquire a blocking advisory lock on ``ui-state.lock``.

    Returns the fd on success or ``None`` when locking is unavailable (missing
    ``fcntl`` or an ``OSError`` while opening/locking). Callers needing strict
    exclusion treat ``None`` as failure; best-effort readers proceed unlocked.
    """

    try:
        import fcntl
    except ImportError:
        logger.debug("fcntl unavailable; proceeding without UI-state lock")
        return None
    try:
        lock_path = ui_state_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as exc:
        logger.debug("Failed to open UI-state lock: %s", exc)
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        return fd
    except OSError as exc:
        logger.debug("Failed to acquire UI-state lock: %s", exc)
        try:
            os.close(fd)
        except OSError:
            pass
        return None


def release_ui_state_lock(fd: int) -> None:
    """Release a lock fd acquired by :func:`acquire_ui_state_lock`."""

    try:
        import fcntl
    except ImportError:
        try:
            os.close(fd)
        except OSError:
            pass
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
