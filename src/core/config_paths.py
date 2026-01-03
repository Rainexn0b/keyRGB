"""Compatibility shim.

`src.core.config_paths` is kept for backward compatibility. New code should
import from `src.core.config.paths`.
"""

from __future__ import annotations

from src.core.config.paths import config_dir, config_file_path

__all__ = ["config_dir", "config_file_path"]
