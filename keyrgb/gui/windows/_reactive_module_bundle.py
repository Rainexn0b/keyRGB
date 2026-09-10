"""Shared import hub for reactive-window submodules.

Centralizes the Reactive Color window's private submodule imports so
``reactive_color.py`` keeps a small leading import block for the File Size
gate. Adds no behavior; every name remains available on ``reactive_color``
via module aliases, preserving monkeypatch seams.
"""

from __future__ import annotations

import logging

from . import (
    _reactive_color_geometry,
    _reactive_color_init_adapter,
    _reactive_color_interactions,
    _reactive_color_settings_adapter,
    _reactive_color_state,
    _reactive_color_ui,
    _reactive_color_wiring,
)

logger = logging.getLogger(__name__)

__all__ = [
    "_reactive_color_geometry",
    "_reactive_color_init_adapter",
    "_reactive_color_interactions",
    "_reactive_color_settings_adapter",
    "_reactive_color_state",
    "_reactive_color_ui",
    "_reactive_color_wiring",
]
