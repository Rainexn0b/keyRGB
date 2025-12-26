#!/usr/bin/env python3
"""
KeyRGB Configuration Manager
Persists settings to JSON file
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path


logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for KeyRGB"""
    
    CONFIG_DIR = Path.home() / '.config' / 'keyrgb'
    CONFIG_FILE = CONFIG_DIR / 'config.json'
    
    DEFAULTS = {
        'effect': 'rainbow',
        'speed': 4,  # 0-10 UI scale (10 = fastest)
        'brightness': 25,  # 0-50 hardware scale
        'color': [255, 0, 0],  # RGB for static/custom effects
        'autostart': True,
        # Per-key colors stored as {"row,col": [r,g,b]}
        'per_key_colors': {}
    }

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:
        """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""
        out = {}
        for (row, col), color in color_map.items():
            try:
                r, g, b = color
                out[f"{int(row)},{int(col)}"] = [int(r), int(g), int(b)]
            except Exception:
                continue
        return out

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:
        """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""
        out = {}
        if not isinstance(data, dict):
            return out
        for k, v in data.items():
            try:
                row_s, col_s = str(k).split(',', 1)
                row = int(row_s.strip())
                col = int(col_s.strip())
                r, g, b = v
                out[(row, col)] = (int(r), int(g), int(b))
            except Exception:
                continue
        return out
    
    def __init__(self):
        """Load configuration"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        self._settings = loaded if loaded is not None else self.DEFAULTS.copy()
    
    def _load(self, *, retries: int = 3, retry_delay: float = 0.02):
        """Load settings from file.

        This may race with writers (tray/GUI) updating the JSON file. We retry a few
        times for transient JSONDecodeError (e.g., if a writer truncated then rewrote).
        Returns None if loading fails after retries.
        """

        if not self.CONFIG_FILE.exists():
            return self.DEFAULTS.copy()

        last_error = None
        for _ in range(max(1, retries)):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                # Normalize effect name to lowercase
                if 'effect' in loaded and isinstance(loaded['effect'], str):
                    loaded['effect'] = loaded['effect'].lower()
                # Merge with defaults for any missing keys
                return {**self.DEFAULTS, **loaded}
            except json.JSONDecodeError as e:
                last_error = e
                time.sleep(retry_delay)
            except Exception as e:
                last_error = e
                break

        logger.warning("Failed to load config: %s", last_error)
        return None
    
    def reload(self):
        """Reload settings from file (e.g., after external changes)"""
        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded
    
    def _save(self):
        """Save settings to file"""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file then replace.
            tmp_fd, tmp_path = tempfile.mkstemp(prefix='config.', suffix='.tmp', dir=str(self.CONFIG_DIR))
            try:
                with os.fdopen(tmp_fd, 'w') as f:
                    json.dump(self._settings, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.CONFIG_FILE)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Failed to save config: %s", e)
    
    @property
    def effect(self) -> str:
        return self._settings['effect']
    
    @effect.setter
    def effect(self, value: str):
        self._settings['effect'] = value.lower()
        self._save()
    
    @property
    def speed(self) -> int:
        return self._settings['speed']
    
    @speed.setter
    def speed(self, value: int):
        self._settings['speed'] = max(0, min(10, value))
        self._save()
    
    @property
    def brightness(self) -> int:
        return self._settings['brightness']
    
    @brightness.setter
    def brightness(self, value: int):
        self._settings['brightness'] = max(0, min(50, value))
        self._save()
    
    @property
    def color(self) -> tuple:
        return tuple(self._settings['color'])
    
    @color.setter
    def color(self, value: tuple):
        self._settings['color'] = list(value)
        self._save()
    
    @property
    def autostart(self) -> bool:
        return self._settings['autostart']
    
    @autostart.setter
    def autostart(self, value: bool):
        self._settings['autostart'] = value
        self._save()

    @property
    def per_key_colors(self) -> dict:
        """Per-key color map as {(row,col): (r,g,b)}."""
        return self._deserialize_per_key_colors(self._settings.get('per_key_colors', {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings['per_key_colors'] = self._serialize_per_key_colors(value or {})
        self._save()
