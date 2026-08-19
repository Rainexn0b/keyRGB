"""KeyRGB Configuration Manager.

This package groups the config manager and related helpers.

Backward compatibility:
- `from keyrgb.core.config import Config` continues to work.

"""

from __future__ import annotations

from .config import Config, ConfigPersistenceError
from .document import ConfigDocument
from .domains import ConfigDomain
from .file_storage import load_config_settings, save_config_settings_atomic
from .paths import config_dir, config_file_path
from .perkey_colors import deserialize_per_key_colors, serialize_per_key_colors

__all__ = [
    "Config",
    "ConfigDocument",
    "ConfigDomain",
    "ConfigPersistenceError",
    "config_dir",
    "config_file_path",
    "deserialize_per_key_colors",
    "load_config_settings",
    "save_config_settings_atomic",
    "serialize_per_key_colors",
]
