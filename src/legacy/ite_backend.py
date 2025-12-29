from __future__ import annotations

"""Legacy compatibility wrapper for the ITE backend.

This module exists to preserve the historical import surface used by
`src/legacy/effects.py` while the codebase migrates to the new backend
registry/selection architecture.

Exports kept stable:
- `get()`
- `NUM_ROWS`, `NUM_COLS`
- `hw_effects`, `hw_colors`
"""

from src.core.backends.registry import select_backend


def _select_backend():
    # Note: selection is intentionally import-based for now (no hardware probe).
    return select_backend()


_backend = _select_backend()


def get():
    if _backend is None:
        raise FileNotFoundError("No keyboard backend available")
    return _backend.get_device()


try:
    if _backend is None:
        raise RuntimeError("No backend")
    NUM_ROWS, NUM_COLS = _backend.dimensions()
    hw_effects = _backend.effects()
    hw_colors = _backend.colors()
except Exception:
    # Keep legacy defaults so imports don't crash when no dependency/hardware.
    NUM_ROWS, NUM_COLS = 6, 21
    hw_effects = {}
    hw_colors = {}

__all__ = ["get", "hw_effects", "hw_colors", "NUM_ROWS", "NUM_COLS"]
