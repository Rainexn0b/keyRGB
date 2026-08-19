"""Cross-process ownership lock for direct keyboard hardware access."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import IO

_hardware_lock_fh: IO[str] | None = None


def _hardware_lock_path() -> Path:
    config_dir = os.environ.get("KEYRGB_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "keyrgb.lock"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "keyrgb" / "keyrgb.lock"
    return Path.home() / ".config" / "keyrgb" / "keyrgb.lock"


def acquire_hardware_control_lock() -> bool:
    """Acquire the process-wide KeyRGB hardware-owner lock without blocking."""

    global _hardware_lock_fh
    if _hardware_lock_fh is not None:
        return True

    try:
        import fcntl
    except ImportError:
        return True

    lock_path = _hardware_lock_path()
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

    lock_fh.seek(0)
    lock_fh.truncate()
    lock_fh.write(f"pid={os.getpid()}\n")
    lock_fh.flush()
    _hardware_lock_fh = lock_fh
    atexit.register(release_hardware_control_lock)
    return True


def release_hardware_control_lock() -> None:
    """Release this process's hardware-owner lock, if held."""

    global _hardware_lock_fh
    lock_fh = _hardware_lock_fh
    _hardware_lock_fh = None
    if lock_fh is not None:
        lock_fh.close()
