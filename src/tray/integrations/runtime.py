from __future__ import annotations

import os
from dataclasses import dataclass
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pystray as _pystray


_pystray_mod = None
_pystray_item = None
_instance_lock_fh = None


@dataclass(frozen=True)
class _PystrayImportFailure:
    reason: str
    original: Exception


def _iter_exc_chain(exc: BaseException, *, max_depth: int = 10):
    cur: BaseException | None = exc
    depth = 0
    while cur is not None and depth < max_depth:
        yield cur
        nxt = cur.__cause__ or cur.__context__
        if nxt is cur:
            break
        cur = nxt
        depth += 1


def _classify_pystray_import_error(exc: Exception) -> _PystrayImportFailure | None:
    """Classify known, recoverable pystray import failures.

    We primarily care about a broken/partial `gi` module causing:
        AttributeError: module 'gi' has no attribute 'require_version'

    In that case, forcing the Xorg backend is typically sufficient.
    """

    for e in _iter_exc_chain(exc):
        if isinstance(e, AttributeError):
            msg = str(e)
            if "module 'gi'" in msg and "require_version" in msg:
                return _PystrayImportFailure(reason="broken-gi", original=exc)
    return None


def _force_pystray_backend_xorg() -> None:
    # Only set if user hasn't explicitly chosen a backend.
    os.environ.setdefault("PYSTRAY_BACKEND", "xorg")


def get_pystray():
    """Import pystray only when the tray UI is actually needed.

    Importing `pystray` on Linux may attempt to connect to an X display
    immediately, which breaks headless environments (like CI) that still
    need to be able to import tray modules.
    """

    global _pystray_mod, _pystray_item

    if _pystray_mod is not None and _pystray_item is not None:
        return _pystray_mod, _pystray_item

    import importlib

    try:
        _pystray_mod = importlib.import_module("pystray")
    except Exception as exc:  # pragma: no cover (depends on desktop env)
        failure = _classify_pystray_import_error(exc)
        if failure and failure.reason == "broken-gi":
            # If a non-PyGObject `gi` module (or a partial/broken install) is found,
            # pystray's AppIndicator backend raises AttributeError during import and
            # does not fall back to other backends. Force Xorg and retry once.
            _force_pystray_backend_xorg()
            _pystray_mod = importlib.import_module("pystray")
        else:
            raise RuntimeError(
                "pystray could not be initialized. The tray app requires a desktop "
                "session (X11/Wayland). In CI/headless environments, importing the "
                "module is supported but running the tray is not."
            ) from exc

    _pystray_item = getattr(_pystray_mod, "MenuItem")
    return _pystray_mod, _pystray_item


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
