"""Compatibility wrapper for default profile data.

The implementation moved to `src.core.resources.defaults` as part of the
purpose-based refactor.
"""

from __future__ import annotations

from src.core.resources.defaults import (
    DEFAULT_COLORS,
    DEFAULT_KEYMAP,
    DEFAULT_LAYOUT_TWEAKS,
    DEFAULT_PER_KEY_TWEAKS,
)

__all__ = [
    "DEFAULT_LAYOUT_TWEAKS",
    "DEFAULT_KEYMAP",
    "DEFAULT_PER_KEY_TWEAKS",
    "DEFAULT_COLORS",
]
