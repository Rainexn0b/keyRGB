from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

_config_logger = logging.getLogger(__name__)

_CONFIG_LOAD_TERMINAL_ERRORS = (OSError, RecursionError, TypeError, ValueError)
_CONFIG_SAVE_ERRORS = (OSError, RecursionError, TypeError, ValueError)


def _log_warning_with_traceback(logger, message: str, exc: Exception) -> None:
    logger.warning(message, exc_info=(type(exc), exc, exc.__traceback__))


def _acquire_lock(config_dir: Path, *, exclusive: bool) -> int | None:
    """Acquire a file lock on config_dir/config.lock.

    Returns the file descriptor if successful, None on failure.
    The caller is responsible for closing the fd.
    """
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        lock_path = config_dir / "config.lock"
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        return None

    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        return fd
    except OSError:
        try:
            os.close(fd)
        except OSError:
            pass
        return None


def _release_lock(fd: int) -> None:
    """Release and close a file lock acquired by _acquire_lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def load_config_settings(
    *,
    config_file: Path,
    defaults: dict[str, Any],
    retries: int = 3,
    retry_delay: float = 0.02,
    logger,
) -> dict[str, Any] | None:
    """Load config JSON with retries for transient partial writes.

    Uses a shared file lock (LOCK_SH) on config_dir/config.lock to prevent
    reads during concurrent writes from other processes (tray, GUI windows).

    Returns a merged dict of `{**defaults, **loaded}` when successful.
    Returns a copy of `defaults` when the file does not exist.
    Returns None when loading fails after retries.
    """

    if not config_file.exists():
        return deepcopy(defaults)

    config_dir = config_file.parent
    lock_fd = _acquire_lock(config_dir, exclusive=False)

    try:
        return _load_config_inner(
            config_file=config_file,
            defaults=defaults,
            retries=retries,
            retry_delay=retry_delay,
            logger=logger,
        )
    finally:
        if lock_fd is not None:
            _release_lock(lock_fd)


def _load_config_inner(
    *,
    config_file: Path,
    defaults: dict[str, Any],
    retries: int,
    retry_delay: float,
    logger,
) -> dict[str, Any] | None:
    """Inner load implementation, called under a shared lock."""
    last_error: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                loaded = {}

            if "effect" in loaded and isinstance(loaded["effect"], str):
                loaded["effect"] = loaded["effect"].lower()

            # Removed older software effects still normalize to a safe supported mode
            # instead of surfacing an unknown-effect failure during startup.
            older_effect_name = loaded.get("effect")
            if older_effect_name in {"static", "pulse"}:
                loaded["effect"] = "none"
            elif older_effect_name in {"breathing_sw", "fire", "random", "rain"}:
                loaded["effect"] = "none"

            if "return_effect_after_effect" in loaded and isinstance(loaded["return_effect_after_effect"], str):
                loaded["return_effect_after_effect"] = loaded["return_effect_after_effect"].lower()

            merged = deepcopy(defaults)
            merged.update(loaded)
            return merged
        except json.JSONDecodeError as e:
            last_error = e
            time.sleep(retry_delay)
        except _CONFIG_LOAD_TERMINAL_ERRORS as e:
            last_error = e
            break

    if last_error is not None:
        _log_warning_with_traceback(logger, "Failed to load config: %s", last_error)
    return None


def save_config_settings_atomic(*, config_dir: Path, config_file: Path, settings: dict[str, Any], logger) -> None:
    """Save config JSON atomically with exclusive file lock.

    Acquires LOCK_EX on config_dir/config.lock, then writes to a temp file
    and atomically replaces the config file via os.replace(). This prevents
    concurrent readers (tray, GUI windows) from seeing a partial write, and
    prevents concurrent writers from interleaving their changes.
    """

    lock_fd = _acquire_lock(config_dir, exclusive=True)
    try:
        _save_config_inner(config_dir=config_dir, config_file=config_file, settings=settings, logger=logger)
    finally:
        if lock_fd is not None:
            _release_lock(lock_fd)


def _save_config_inner(*, config_dir: Path, config_file: Path, settings: dict[str, Any], logger) -> None:
    """Inner save implementation, called under an exclusive lock."""
    try:
        config_dir.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=str(config_dir))
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, config_file)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError as exc:
                logger.debug("Failed to remove temp config file %s: %s", tmp_path, exc)

    except _CONFIG_SAVE_ERRORS as e:
        _log_warning_with_traceback(logger, "Failed to save config: %s", e)
