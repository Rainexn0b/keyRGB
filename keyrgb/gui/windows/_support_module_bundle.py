"""Shared import hub for support-window submodules.

Centralizes the Support Tools window's private ``_support`` submodule imports
so ``support.py`` keeps a small leading import block for the File Size gate.
Adds no behavior; every name remains available on ``support`` via module
aliases, preserving monkeypatch seams.
"""

from __future__ import annotations

import logging

from ._support import (
    _support_window_actions,
    _support_window_geometry,
    _support_window_jobs,
    _support_window_runtime_services,
    _support_window_session_bridge,
    _support_window_state,
    _support_window_ui,
)

logger = logging.getLogger(__name__)

__all__ = [
    "_support_window_actions",
    "_support_window_geometry",
    "_support_window_jobs",
    "_support_window_runtime_services",
    "_support_window_session_bridge",
    "_support_window_state",
    "_support_window_ui",
]
