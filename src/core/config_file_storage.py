"""Compatibility shim.

`src.core.config_file_storage` is kept for backward compatibility. New code
should import from `src.core.config.file_storage`.
"""

from __future__ import annotations

from src.core.config.file_storage import load_config_settings, save_config_settings_atomic

__all__ = ["load_config_settings", "save_config_settings_atomic"]
