"""Compatibility shim.

`src.core.config_defaults` is kept for backward compatibility. New code should
import from `src.core.config.defaults`.
"""

from __future__ import annotations

from src.core.config.defaults import DEFAULTS

__all__ = ["DEFAULTS"]
