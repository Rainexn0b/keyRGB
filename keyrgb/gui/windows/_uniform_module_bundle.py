"""Shared import hub for uniform-window submodules.

Centralizes the Uniform Color window's private submodule imports (plus the
bottom-most shared-widget imports) so ``uniform.py`` keeps a small leading
import block for the File Size gate. Adds no behavior; every name remains
available on ``uniform`` via module aliases, preserving monkeypatch seams.
"""

from __future__ import annotations

import logging

from keyrgb.gui.utils.window_icon import apply_keyrgb_window_icon
from keyrgb.gui.utils.window_state import WindowGeometryTracker
from keyrgb.gui.widgets.color_wheel import ColorWheel

from . import (
    _uniform_color_bootstrap,
    _uniform_color_interactions,
    _uniform_color_state,
    _uniform_color_ui,
    _uniform_init_adapter,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ColorWheel",
    "WindowGeometryTracker",
    "_uniform_color_bootstrap",
    "_uniform_color_interactions",
    "_uniform_color_state",
    "_uniform_color_ui",
    "_uniform_init_adapter",
    "apply_keyrgb_window_icon",
]
