from __future__ import annotations

import atexit
import os
import sys
import importlib
import importlib.util
import logging
from dataclasses import dataclass
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


_pystray_mod = None
_pystray_item = None
_instance_lock_fh = None
_gtk_log_handler_id = None
_appindicator_log_handler_id = None


logger = logging.getLogger(__name__)

_PYSTRAY_IMPORT_RUNTIME_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)


_GI_PROBE_EXCEPTIONS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_PYSTRAY_IMPORT_RETRY_EXCEPTIONS = _GI_PROBE_EXCEPTIONS


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


def _set_pystray_backend_xorg_for_retry() -> None:
    # Used for automatic selection and retry paths.
    os.environ["PYSTRAY_BACKEND"] = "xorg"


def _set_pystray_backend_gtk_for_retry() -> None:
    os.environ["PYSTRAY_BACKEND"] = "gtk"


def _set_pystray_backend_appindicator_for_retry() -> None:
    os.environ["PYSTRAY_BACKEND"] = "appindicator"


def _install_log_filter_for_backend(backend: str) -> None:
    if backend == "gtk":
        _install_gtk_scale_factor_log_filter()
    elif backend == "appindicator":
        _install_appindicator_deprecation_log_filter()


def _configure_backend_for_import(backend: str) -> None:
    if backend == "gtk":
        _set_pystray_backend_gtk_for_retry()
    elif backend == "appindicator":
        _set_pystray_backend_appindicator_for_retry()
    elif backend == "xorg":
        _set_pystray_backend_xorg_for_retry()
    else:  # pragma: no cover - auto-selection only uses known backends
        raise ValueError(f"Unsupported pystray backend: {backend}")
    _install_log_filter_for_backend(backend)


def _is_kde_wayland_session() -> bool:
    session_type = str(os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    current_desktop = str(os.environ.get("XDG_CURRENT_DESKTOP") or "").strip().lower()
    desktop_session = str(os.environ.get("DESKTOP_SESSION") or "").strip().lower()
    return session_type == "wayland" and ("kde" in current_desktop or "plasma" in desktop_session)


def _is_gnome_session() -> bool:
    """Return True when running inside a GNOME Shell session.

    GNOME Shell dropped the legacy XEmbed system-tray protocol around GNOME 3.26,
    so pystray's ``gtk`` backend (GtkStatusIcon) is invisible there regardless of
    what extensions are installed.  The AppIndicator/SNI extension only helps
    clients that use the ``appindicator`` (SNI/DBus) backend.
    """
    current_desktop = str(os.environ.get("XDG_CURRENT_DESKTOP") or "").strip().lower()
    desktop_session = str(os.environ.get("DESKTOP_SESSION") or "").strip().lower()
    return "gnome" in current_desktop or "gnome" in desktop_session


def _install_gtk_scale_factor_log_filter() -> None:
    global _gtk_log_handler_id

    if _gtk_log_handler_id is not None:
        return

    try:
        gi = importlib.import_module("gi")
        gi.require_version("GLib", "2.0")
        glib = importlib.import_module("gi.repository.GLib")
    except _GI_PROBE_EXCEPTIONS:
        return

    if not all(hasattr(glib, attr) for attr in ("log_default_handler", "log_set_handler", "LogLevelFlags")):
        return

    def _handler(domain, level, message, user_data):
        domain_text = "" if domain is None else str(domain)
        message_text = "" if message is None else str(message)
        if domain_text == "Gtk" and "gtk_widget_get_scale_factor" in message_text:
            return
        glib.log_default_handler(domain, level, message, user_data)

    _gtk_log_handler_id = glib.log_set_handler("Gtk", glib.LogLevelFlags.LEVEL_CRITICAL, _handler, None)


def _install_appindicator_deprecation_log_filter() -> None:
    global _appindicator_log_handler_id

    if _appindicator_log_handler_id is not None:
        return

    try:
        gi = importlib.import_module("gi")
        gi.require_version("GLib", "2.0")
        glib = importlib.import_module("gi.repository.GLib")
    except _GI_PROBE_EXCEPTIONS:
        return

    if not all(hasattr(glib, attr) for attr in ("log_default_handler", "log_set_handler", "LogLevelFlags")):
        return

    def _handler(domain, level, message, user_data):
        domain_text = "" if domain is None else str(domain)
        message_text = "" if message is None else str(message)
        if domain_text == "libayatana-appindicator" and "is deprecated" in message_text:
            return
        glib.log_default_handler(domain, level, message, user_data)

    _appindicator_log_handler_id = glib.log_set_handler(
        "libayatana-appindicator", glib.LogLevelFlags.LEVEL_WARNING, _handler, None
    )


def _gi_is_working() -> bool:
    """Return True if PyGObject appears usable.

    Some environments have a shadowing/broken `gi` module which lacks
    `require_version`, which breaks pystray's AppIndicator backend.
    """

    # Avoid a static `import gi` so build/import scanning tools don't treat it as
    # a hard dependency. We only need gi when the AppIndicator backend is viable.
    try:
        spec = importlib.util.find_spec("gi")
        if spec is None:
            return False
        gi = importlib.import_module("gi")
        return hasattr(gi, "require_version")
    except _GI_PROBE_EXCEPTIONS:
        return False


def _clear_failed_import(name: str) -> None:
    # If an import fails, Python may leave a partially-initialized module around.
    # Clear it so a backend retry gets a clean import attempt.
    sys.modules.pop(name, None)


def _import_pystray_with_fallbacks(
    candidates: list[tuple[str, str]],
    *,
    import_module=None,
):
    if import_module is None:
        import_module = importlib.import_module

    last_exc: Exception | None = None

    for attempt, (backend, log_label) in enumerate(candidates):
        if attempt > 0:
            _clear_failed_import("pystray")
        _configure_backend_for_import(backend)
        logger.info("pystray backend: %s", log_label)
        try:
            return import_module("pystray")
        except _PYSTRAY_IMPORT_RETRY_EXCEPTIONS as exc:
            last_exc = exc

    assert last_exc is not None
    raise RuntimeError(
        "pystray could not be initialized. The tray app requires a desktop "
        "session (X11/Wayland). In CI/headless environments, importing the "
        "module is supported but running the tray is not."
    ) from last_exc


def _auto_backend_candidates(*, gi_working: bool) -> list[tuple[str, str]]:
    if not gi_working:
        return [("xorg", "xorg (auto)")]
    if _is_kde_wayland_session():
        return [
            ("appindicator", "appindicator (auto-kde-wayland)"),
            ("gtk", "gtk (appindicator fallback)"),
            ("xorg", "xorg (gtk fallback)"),
        ]
    if _is_gnome_session():
        # GNOME Shell dropped XEmbed trays around 3.26; GtkStatusIcon is invisible.
        # The AppIndicator/kStatusNotifierItem extension handles SNI/DBus icons,
        # which is what the appindicator pystray backend uses.
        return [
            ("appindicator", "appindicator (auto-gnome)"),
            ("gtk", "gtk (appindicator fallback)"),
            ("xorg", "xorg (gtk fallback)"),
        ]
    return [
        ("gtk", "gtk (auto)"),
        ("xorg", "xorg (gtk fallback)"),
        ("appindicator", "appindicator (xorg fallback)"),
    ]


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

    # Backend selection strategy:
    # - Respect explicit user choice via PYSTRAY_BACKEND.
    # - On KDE Wayland, prefer AppIndicator so the tray icon stays visible.
    # - Otherwise, prefer GTK automatically when PyGObject is usable so the tray keeps a shaped icon.
    # - Fall back to Xorg when the preferred desktop-native path fails.
    # - Keep the remaining backend as a final compatibility path.
    explicit_backend = "PYSTRAY_BACKEND" in os.environ

    if not explicit_backend:
        _pystray_mod = _import_pystray_with_fallbacks(_auto_backend_candidates(gi_working=_gi_is_working()))
    else:
        try:
            if explicit_backend:
                backend = os.environ.get("PYSTRAY_BACKEND")
                if backend is not None:
                    _install_log_filter_for_backend(backend)
                logger.info("pystray backend: %s (explicit)", backend)
            _pystray_mod = importlib.import_module("pystray")
        # @quality-exception exception-transparency: pystray import is a runtime desktop-env boundary; broken-gi is classified and retried with xorg fallback
        except _PYSTRAY_IMPORT_RUNTIME_ERRORS as exc:  # pragma: no cover (depends on desktop env)
            failure = _classify_pystray_import_error(exc)
            if failure and failure.reason == "broken-gi":
                # If a non-PyGObject `gi` module (or a partial/broken install) is found,
                # pystray's AppIndicator backend raises AttributeError during import and
                # does not fall back to other backends. Force Xorg and retry once.
                _pystray_mod = _import_pystray_with_fallbacks([("xorg", "xorg (broken-gi fallback)")])
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
    except ImportError:
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
    with suppress(OSError):
        lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "keyrgb.lock"

    try:
        _instance_lock_fh = open(lock_path, "a+")
        fcntl.flock(_instance_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        atexit.register(_instance_lock_fh.close)
        _instance_lock_fh.seek(0)
        _instance_lock_fh.truncate()
        _instance_lock_fh.write(f"pid={os.getpid()}\n")
        _instance_lock_fh.flush()
        return True
    except OSError:
        return False
