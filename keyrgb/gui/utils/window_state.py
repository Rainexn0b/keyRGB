"""Tk-free persistence for main-window geometry (UX-06).

This module is the single owner of ``config_dir()/ui-state.json`` window
geometry. It never touches ``config.json`` (so tray config watchers stay
quiet) and never imports Tkinter: the :class:`WindowGeometryTracker` drives a
caller-provided root through duck-typed ``winfo_*``/``geometry``/``bind``/
``after`` methods.

Storage layout preserves sibling and unknown top-level state::

    {"windows": {"settings": {"width": 880, "height": 840, "x": 100, "y": 80}},
     ...unknown keys preserved...}

Position (``x``/``y``) is best-effort on Wayland: saves omit coordinates when
``WAYLAND_DISPLAY`` is set or ``XDG_SESSION_TYPE=wayland``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeGuard, cast

from keyrgb.core.config.paths import config_dir

logger = logging.getLogger(__name__)

__all__ = [
    "WindowGeometry",
    "WindowGeometryTracker",
    "geometry_string",
    "load_window_geometry",
    "prepare_restored_geometry",
    "save_window_geometry",
    "ui_state_lock_path",
    "ui_state_path",
]

_UI_STATE_FILENAME = "ui-state.json"
_UI_STATE_LOCK_FILENAME = "ui-state.lock"

_STATIC_WINDOW_IDS = frozenset(
    {
        "settings",
        "reactive-color",
        "power-mode",
        "support",
        "perkey",
        "calibrator",
    }
)
_UNIFORM_WINDOW_ID_RE = re.compile(r"uniform-[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_MAX_DIMENSION_PX = 16384
_MAX_COORD_ABS_PX = 32768

_STATE_LOAD_ERRORS = (OSError, ValueError, TypeError)
_STATE_SAVE_ERRORS = (OSError, ValueError, TypeError)


class _WindowRootProtocol(Protocol):
    def geometry(self, value: str) -> object: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...

    def winfo_width(self) -> int: ...

    def winfo_height(self) -> int: ...

    def winfo_x(self) -> int: ...

    def winfo_y(self) -> int: ...

    def bind(self, sequence: str, callback: Callable[[object], object], add: object = None) -> object: ...

    def after(self, delay_ms: int, callback: Callable[[], object]) -> object: ...

    def after_cancel(self, after_id: object) -> object: ...


@dataclass(frozen=True)
class WindowGeometry:
    """Validated window size with optional position."""

    width: int
    height: int
    x: int | None = None
    y: int | None = None


def ui_state_path() -> Path:
    """Return the UI-state JSON path (``config_dir()/ui-state.json``)."""
    return config_dir() / _UI_STATE_FILENAME


def ui_state_lock_path() -> Path:
    """Return the UI-state advisory-lock path (distinct from the JSON file)."""
    return config_dir() / _UI_STATE_LOCK_FILENAME


def _normalize_window_id(window_id: object) -> str | None:
    if not isinstance(window_id, str):
        return None
    normalized = window_id.lower()
    if normalized in _STATIC_WINDOW_IDS:
        return normalized
    if _UNIFORM_WINDOW_ID_RE.fullmatch(normalized) is not None:
        return normalized
    return None


def _is_wayland() -> bool:
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower() == "wayland"


def _acquire_ui_state_lock(*, exclusive: bool) -> int | None:
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


def _release_ui_state_lock(fd: int) -> None:
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


def _is_valid_dimension(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= _MAX_DIMENSION_PX


def _is_valid_coord(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and abs(value) <= _MAX_COORD_ABS_PX


def _parse_geometry_entry(raw: object) -> WindowGeometry | None:
    if not isinstance(raw, dict):
        return None
    raw_entry = cast(dict[str, object], raw)
    width_raw = raw_entry.get("width")
    height_raw = raw_entry.get("height")
    if not _is_valid_dimension(width_raw) or not _is_valid_dimension(height_raw):
        return None
    width_px = int(width_raw)
    height_px = int(height_raw)
    x_raw = raw_entry.get("x", None)
    y_raw = raw_entry.get("y", None)
    if x_raw is None and y_raw is None:
        return WindowGeometry(width=width_px, height=height_px)
    if not _is_valid_coord(x_raw) or not _is_valid_coord(y_raw):
        return None
    return WindowGeometry(width=width_px, height=height_px, x=int(x_raw), y=int(y_raw))


def _read_state_unlocked(state_path: Path) -> dict[str, object] | None:
    try:
        with state_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except _STATE_LOAD_ERRORS as exc:
        logger.warning("Failed to load UI state %s: %s", state_path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("Ignoring malformed UI state %s: top level is not an object", state_path)
        return None
    return cast(dict[str, object], data)


def _write_state_atomic(state_path: Path, state: dict[str, object]) -> bool:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=".ui-state.", suffix=".tmp", dir=str(state_path.parent))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, state_path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError as exc:
                logger.debug("Failed to remove temp UI-state file %s: %s", tmp_name, exc)
        return True
    except _STATE_SAVE_ERRORS as exc:
        logger.warning("Failed to save UI state %s: %s", state_path, exc)
        return False


def load_window_geometry(window_id: str) -> WindowGeometry | None:
    """Return the stored geometry for *window_id* or ``None``.

    Unknown window IDs, a missing/corrupt state file, and malformed or absurd
    entries all fall back to ``None`` without raising.
    """
    normalized = _normalize_window_id(window_id)
    if normalized is None:
        logger.debug("Ignoring UI-state load for invalid window id %r", window_id)
        return None
    state_path = ui_state_path()
    lock_fd = _acquire_ui_state_lock(exclusive=False)
    try:
        if not state_path.exists():
            return None
        data = _read_state_unlocked(state_path)
        if data is None:
            return None
        windows = data.get("windows")
        if not isinstance(windows, dict):
            return None
        return _parse_geometry_entry(windows.get(normalized))
    finally:
        if lock_fd is not None:
            _release_ui_state_lock(lock_fd)


def save_window_geometry(window_id: str, geometry: WindowGeometry) -> bool:
    """Persist *geometry* for *window_id* via locked read-modify-write.

    Sibling window entries and unknown top-level keys are preserved. On
    Wayland only the size is stored; elsewhere ``x``/``y`` are stored when the
    geometry carries both. Returns ``True`` on success.
    """
    normalized = _normalize_window_id(window_id)
    if normalized is None:
        logger.debug("Ignoring UI-state save for invalid window id %r", window_id)
        return False
    if not isinstance(geometry, WindowGeometry):
        logger.debug("Ignoring UI-state save with invalid geometry type %r", type(geometry))
        return False
    if not _is_valid_dimension(geometry.width) or not _is_valid_dimension(geometry.height):
        logger.debug("Ignoring UI-state save with invalid size %r", geometry)
        return False
    has_position = geometry.x is not None or geometry.y is not None
    if has_position and (not _is_valid_coord(geometry.x) or not _is_valid_coord(geometry.y)):
        logger.debug("Ignoring UI-state save with invalid position %r", geometry)
        return False

    if _is_wayland():
        payload: dict[str, object] = {"width": geometry.width, "height": geometry.height}
    elif geometry.x is None or geometry.y is None:
        payload = {"width": geometry.width, "height": geometry.height}
    else:
        payload = {"width": geometry.width, "height": geometry.height, "x": geometry.x, "y": geometry.y}

    lock_fd = _acquire_ui_state_lock(exclusive=True)
    if lock_fd is None:
        try:
            import fcntl  # noqa: F401
        except ImportError:
            pass
        else:
            logger.warning("Failed to save UI state: could not acquire UI-state lock")
            return False
    try:
        state_path = ui_state_path()
        if state_path.exists():
            data = _read_state_unlocked(state_path)
            if data is None:
                # Corrupt on-disk state must not block future saves; start fresh.
                data = {}
        else:
            data = {}
        windows_raw = data.get("windows")
        if not isinstance(windows_raw, dict):
            windows: dict[str, object] = {}
            data["windows"] = windows
        else:
            windows = cast(dict[str, object], windows_raw)
        windows[normalized] = payload
        return _write_state_atomic(state_path, data)
    finally:
        if lock_fd is not None:
            _release_ui_state_lock(lock_fd)


def prepare_restored_geometry(
    saved: WindowGeometry | None,
    screen_width: int,
    screen_height: int,
    min_width: int,
    min_height: int,
    screen_ratio_cap: float = 0.95,
) -> WindowGeometry | None:
    """Clamp *saved* to the current screen or reject it with ``None``.

    Malformed/absurd sizes, unusable screen/minimum inputs, and wholly
    off-screen positions return ``None`` so callers fall back to centered
    geometry. Valid sizes are clamped up to the window minimum and down to the
    screen work-area cap; size-only entries restore without coordinates.
    """
    if saved is None or not isinstance(saved, WindowGeometry):
        return None
    if isinstance(screen_width, bool) or isinstance(screen_height, bool):
        return None
    if isinstance(min_width, bool) or isinstance(min_height, bool):
        return None
    try:
        screen_w = int(screen_width)
        screen_h = int(screen_height)
        floor_w = int(min_width)
        floor_h = int(min_height)
        cap = float(screen_ratio_cap)
    except (TypeError, ValueError):
        return None
    if screen_w <= 0 or screen_h <= 0 or floor_w <= 0 or floor_h <= 0:
        return None
    if not 0.0 < cap <= 1.0:
        return None
    if not _is_valid_dimension(saved.width) or not _is_valid_dimension(saved.height):
        return None

    max_w = max(1, int(screen_w * cap))
    max_h = max(1, int(screen_h * cap))
    # The screen cap wins when a display is smaller than the normal minimum;
    # keeping the whole window reachable is more useful than enforcing a
    # minimum that cannot fit on the current display.
    clamped_w = min(max(saved.width, floor_w), max_w)
    clamped_h = min(max(saved.height, floor_h), max_h)

    if saved.x is None and saved.y is None:
        return WindowGeometry(width=clamped_w, height=clamped_h)
    if saved.x is None or saved.y is None:
        return None
    if not _is_valid_coord(saved.x) or not _is_valid_coord(saved.y):
        return None
    x = saved.x
    y = saved.y
    if x + clamped_w <= 0 or y + clamped_h <= 0 or x >= screen_w or y >= screen_h:
        return None
    return WindowGeometry(width=clamped_w, height=clamped_h, x=x, y=y)


def geometry_string(geometry: WindowGeometry) -> str:
    """Return a Tk geometry string for *geometry* (size-only without x/y)."""
    if geometry.x is None or geometry.y is None:
        return f"{geometry.width}x{geometry.height}"
    return f"{geometry.width}x{geometry.height}{geometry.x:+d}{geometry.y:+d}"


class WindowGeometryTracker:
    """Restore once, then debounce ``<Configure>`` writes for one window.

    ``start_tracking`` only binds ``<Configure>`` and must be called after the
    window's initial programmatic geometry passes so centering/restoration is
    not immediately overwritten. The callback ignores bubbled descendant
    events (``event.widget is root``), debounces ``debounce_ms`` via
    ``after``/``after_cancel``, and captures ``winfo_width``/``height``/``x``/
    ``y`` when the timer fires. ``save_now`` cancels any pending write and
    persists synchronously for orderly close.
    """

    def __init__(
        self,
        root: object,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> None:
        self._root = cast(_WindowRootProtocol, root)
        self._window_id = window_id
        self._min_width = int(min_width)
        self._min_height = int(min_height)
        self._screen_ratio_cap = float(screen_ratio_cap)
        self._debounce_ms = int(debounce_ms)
        self._pending_after_id: object | None = None
        self._bound = False

    def restore(self) -> bool:
        """Apply the stored geometry, returning ``True`` when restored."""
        saved = load_window_geometry(self._window_id)
        if saved is None:
            return False
        try:
            screen_w = int(self._root.winfo_screenwidth())
            screen_h = int(self._root.winfo_screenheight())
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and reported as no-restore
            logger.debug("UI-state restore cannot read screen size: %s", exc)
            return False
        prepared = prepare_restored_geometry(
            saved,
            screen_w,
            screen_h,
            self._min_width,
            self._min_height,
            self._screen_ratio_cap,
        )
        if prepared is None:
            return False
        try:
            self._root.geometry(geometry_string(prepared))
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and reported as no-restore
            logger.debug("UI-state restore cannot apply geometry: %s", exc)
            return False
        return True

    def start_tracking(self) -> None:
        """Bind ``<Configure>`` persistence; call after initial geometry."""
        if self._bound:
            return
        try:
            self._root.bind("<Configure>", self._on_configure, add="+")
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and tracking continues unbound
            logger.debug("UI-state tracking cannot bind Configure: %s", exc)
        self._bound = True

    def _on_configure(self, event: object | None = None) -> None:
        widget = getattr(event, "widget", None)
        if widget is not self._root:
            return
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._pending_after_id is not None:
            try:
                self._root.after_cancel(self._pending_after_id)
            except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and the stale timer is dropped
                logger.debug("UI-state tracking cannot cancel pending save: %s", exc)
            self._pending_after_id = None
        try:
            self._pending_after_id = self._root.after(int(self._debounce_ms), self._save_from_widgets)
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and no write is scheduled
            logger.debug("UI-state tracking cannot schedule save: %s", exc)
            self._pending_after_id = None

    def _save_from_widgets(self) -> bool:
        self._pending_after_id = None
        try:
            width = int(self._root.winfo_width())
            height = int(self._root.winfo_height())
            x = int(self._root.winfo_x())
            y = int(self._root.winfo_y())
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged and reported as no-save
            logger.debug("UI-state save cannot read widget geometry: %s", exc)
            return False
        return bool(save_window_geometry(self._window_id, WindowGeometry(width=width, height=height, x=x, y=y)))

    def save_now(self) -> bool:
        """Cancel any pending debounced write and persist synchronously."""
        if self._pending_after_id is not None:
            try:
                self._root.after_cancel(self._pending_after_id)
            except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary must stay Tk-free so TclError cannot be named; failure is debug-logged before the synchronous write
                logger.debug("UI-state save_now cannot cancel pending save: %s", exc)
            self._pending_after_id = None
        return self._save_from_widgets()
