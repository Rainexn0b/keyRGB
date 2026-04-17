from __future__ import annotations

from src.core.backends.registry import select_backend
from src.core.config import Config
from src.gui.theme import apply_clam_theme
from src.gui.utils.window_geometry import compute_centered_window_geometry
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.widgets.color_wheel import ColorWheel
from src.gui.windows import _reactive_color_bootstrap as reactive_color_bootstrap
from src.gui.windows import _reactive_color_interactions as reactive_color_interactions
from src.gui.windows import _reactive_color_ui as reactive_color_ui
from src.gui.windows._reactive_color_state import (
    commit_brightness_to_config,
    commit_color_to_config,
    commit_trail_to_config,
    read_reactive_brightness_percent,
    read_reactive_trail_percent,
    sync_color_wheel_brightness,
    sync_reactive_brightness_widgets,
    sync_reactive_trail_widgets,
)

__all__ = [
    "ColorWheel",
    "Config",
    "apply_clam_theme",
    "apply_keyrgb_window_icon",
    "commit_brightness_to_config",
    "commit_color_to_config",
    "commit_trail_to_config",
    "compute_centered_window_geometry",
    "reactive_color_bootstrap",
    "reactive_color_interactions",
    "reactive_color_ui",
    "read_reactive_brightness_percent",
    "read_reactive_trail_percent",
    "select_backend",
    "sync_color_wheel_brightness",
    "sync_reactive_brightness_widgets",
    "sync_reactive_trail_widgets",
]
