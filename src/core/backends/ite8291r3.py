"""Compatibility wrapper for ITE 8291r3 backend.

The implementation moved to `src.core.backends.ite.backend` as part of the
purpose-based backend refactor.
"""

from __future__ import annotations

from .ite import Ite8291r3Backend

__all__ = ["Ite8291r3Backend"]
