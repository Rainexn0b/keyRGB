"""Shared GUI helper utilities.

This package centralizes small, reusable Tk helpers that are used across multiple
windows.
"""

from __future__ import annotations

from .tk_async import run_in_thread
from .window_centering import center_window_on_screen
from .window_geometry import compute_centered_window_geometry
from .window_icon import apply_keyrgb_window_icon, find_keyrgb_logo_path
from .key_draw_style import KeyDrawStyle, key_draw_style
from .profile_backdrop_storage import (
    load_backdrop_image,
    reset_backdrop_image,
    save_backdrop_image,
)

__all__ = [
    "apply_keyrgb_window_icon",
    "center_window_on_screen",
    "find_keyrgb_logo_path",
    "KeyDrawStyle",
    "key_draw_style",
    "compute_centered_window_geometry",
    "load_backdrop_image",
    "reset_backdrop_image",
    "run_in_thread",
    "save_backdrop_image",
]
