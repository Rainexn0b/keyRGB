"""Compatibility shim.

`src.core.config_perkey_colors` is kept for backward compatibility. New code
should import from `src.core.config.perkey_colors`.
"""

from __future__ import annotations

from src.core.config.perkey_colors import deserialize_per_key_colors, serialize_per_key_colors

__all__ = ["serialize_per_key_colors", "deserialize_per_key_colors"]
