"""Config path helpers.

Kept separate from the main Config object so the public config API stays small
and the Config module remains under the maintenance LOC target.
"""

from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    """Return the directory used for KeyRGB configuration.

    Priority:
    - KEYRGB_CONFIG_DIR
    - XDG_CONFIG_HOME/keyrgb
    - ~/.config/keyrgb
    """

    p = os.environ.get("KEYRGB_CONFIG_DIR")
    if p:
        return Path(p)

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "keyrgb"

    return Path.home() / ".config" / "keyrgb"


def config_file_path() -> Path:
    """Return the KeyRGB config.json path.

    Priority:
    - KEYRGB_CONFIG_PATH (explicit file override)
    - config_dir()/config.json
    """

    p = os.environ.get("KEYRGB_CONFIG_PATH")
    if p:
        return Path(p)
    return config_dir() / "config.json"
