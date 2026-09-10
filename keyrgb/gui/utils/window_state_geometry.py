"""Window-geometry value objects and screen-clamping helpers (UX-06).

Owns the ``WindowGeometry`` value type, window-id normalization, validation,
stored-entry parsing, restore clamping, and Tk geometry formatting so
``window_state.py`` stays small. Tk-free and side-effect free. Adds no
behavior.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TypeGuard, cast

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


@dataclass(frozen=True)
class WindowGeometry:
    """Validated window size with optional position."""

    width: int
    height: int
    x: int | None = None
    y: int | None = None


def normalize_window_id(window_id: object) -> str | None:
    """Return the canonical window id or ``None`` when unknown."""

    if not isinstance(window_id, str):
        return None
    normalized = window_id.lower()
    if normalized in _STATIC_WINDOW_IDS:
        return normalized
    if _UNIFORM_WINDOW_ID_RE.fullmatch(normalized) is not None:
        return normalized
    return None


def is_wayland() -> bool:
    """Return ``True`` when running under a Wayland session."""

    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower() == "wayland"


def is_valid_dimension(value: object) -> TypeGuard[int]:
    """Return ``True`` for sane on-screen window dimensions."""

    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= _MAX_DIMENSION_PX


def is_valid_coord(value: object) -> TypeGuard[int]:
    """Return ``True`` for sane on-screen window coordinates."""

    return isinstance(value, int) and not isinstance(value, bool) and abs(value) <= _MAX_COORD_ABS_PX


def parse_geometry_entry(raw: object) -> WindowGeometry | None:
    """Parse a stored ``windows`` entry or return ``None`` when malformed."""

    if not isinstance(raw, dict):
        return None
    raw_entry = cast(dict[str, object], raw)
    width_raw = raw_entry.get("width")
    height_raw = raw_entry.get("height")
    if not is_valid_dimension(width_raw) or not is_valid_dimension(height_raw):
        return None
    width_px = int(width_raw)
    height_px = int(height_raw)
    x_raw = raw_entry.get("x", None)
    y_raw = raw_entry.get("y", None)
    if x_raw is None and y_raw is None:
        return WindowGeometry(width=width_px, height=height_px)
    if not is_valid_coord(x_raw) or not is_valid_coord(y_raw):
        return None
    return WindowGeometry(width=width_px, height=height_px, x=int(x_raw), y=int(y_raw))


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
    screen work-area cap; size-only entries are centered on the current screen
    so Wayland restores do not land top-left.
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
    if not is_valid_dimension(saved.width) or not is_valid_dimension(saved.height):
        return None

    max_w = max(1, int(screen_w * cap))
    max_h = max(1, int(screen_h * cap))
    # The screen cap wins when a display is smaller than the normal minimum;
    # keeping the whole window reachable is more useful than enforcing a
    # minimum that cannot fit on the current display.
    clamped_w = min(max(saved.width, floor_w), max_w)
    clamped_h = min(max(saved.height, floor_h), max_h)

    if saved.x is None and saved.y is None:
        centered_x = (screen_w - clamped_w) // 2
        centered_y = (screen_h - clamped_h) // 2
        return WindowGeometry(width=clamped_w, height=clamped_h, x=centered_x, y=centered_y)
    if saved.x is None or saved.y is None:
        return None
    if not is_valid_coord(saved.x) or not is_valid_coord(saved.y):
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
