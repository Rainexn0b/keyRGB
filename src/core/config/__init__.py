#!/usr/bin/env python3
"""KeyRGB Configuration Manager.

This package groups the config manager and related helpers.

Backward compatibility:
- `from src.core.config import Config` continues to work.

"""

from __future__ import annotations

from .config import Config
from .file_storage import load_config_settings, save_config_settings_atomic
from .paths import config_dir, config_file_path
from .perkey_colors import deserialize_per_key_colors, serialize_per_key_colors


__all__ = [
    "Config",
    "config_dir",
    "config_file_path",
    "load_config_settings",
    "save_config_settings_atomic",
    "serialize_per_key_colors",
    "deserialize_per_key_colors",
]
