from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pystray as _pystray


_pystray_mod = None
_pystray_item = None
_instance_lock_fh = None


def get_pystray():
    """Import pystray only when the tray UI is actually needed.

    Importing `pystray` on Linux may attempt to connect to an X display
    immediately, which breaks headless environments (like CI) that still
    need to be able to import tray modules.
    """

    global _pystray_mod, _pystray_item

    if _pystray_mod is not None and _pystray_item is not None:
        return _pystray_mod, _pystray_item

    try:
        import importlib

        _pystray_mod = importlib.import_module("pystray")
        _pystray_item = getattr(_pystray_mod, "MenuItem")
        return _pystray_mod, _pystray_item
    except Exception as exc:  # pragma: no cover (depends on desktop env)
        raise RuntimeError(
            "pystray could not be initialized. The tray app requires a desktop "
            "session (X11/Wayland). In CI/headless environments, importing the "
            "module is supported but running the tray is not."
        ) from exc


def acquire_single_instance_lock() -> bool:
    """Ensure only one KeyRGB tray app controls the USB device."""

    global _instance_lock_fh

    try:
        import fcntl  # Linux/Unix
    except Exception:
        return True

    lock_dir = None
    cfg = os.environ.get("KEYRGB_CONFIG_DIR")
    if cfg:
        lock_dir = Path(cfg)
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            lock_dir = Path(xdg) / "keyrgb"
        else:
            lock_dir = Path.home() / ".config" / "keyrgb"
    with suppress(Exception):
        lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "keyrgb.lock"

    try:
        _instance_lock_fh = open(lock_path, "a+")
        fcntl.flock(_instance_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _instance_lock_fh.seek(0)
        _instance_lock_fh.truncate()
        _instance_lock_fh.write(f"pid={os.getpid()}\n")
        _instance_lock_fh.flush()
        return True
    except OSError:
        return False
