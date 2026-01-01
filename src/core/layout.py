"""Compatibility wrapper for GUI layout definitions.

The implementation moved to `src.core.resources.layout` as part of the
purpose-based refactor.
"""

from __future__ import annotations

from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef, Y15_PRO_KEYS, build_layout

__all__ = [
    "KeyDef",
    "BASE_IMAGE_SIZE",
    "Y15_PRO_KEYS",
    "build_layout",
]
