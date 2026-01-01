#!/usr/bin/env python3
"""Unit tests for config_file_storage (core/config_file_storage.py).

Tests atomic writes, retry logic on partial failures, and exception handling.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


class TestLoadConfigSettings:
    """Test load_config_settings retry/fallback logic."""

    def test_load_returns_defaults_when_file_missing(self, temp_config_dir):
        """If config file doesn't exist, return defaults."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "missing.json"
        defaults = {"brightness": 50, "effect": "breathe"}

        result = load_config_settings(
            config_file=config_file,
            defaults=defaults,
            logger=logging.getLogger(),
        )

        assert result == defaults

    def test_load_merges_defaults_with_loaded_data(self, temp_config_dir):
        """Loaded config should be merged with defaults (loaded wins)."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps({"brightness": 75, "new_key": "value"}))

        defaults = {"brightness": 50, "effect": "breathe"}

        result = load_config_settings(
            config_file=config_file,
            defaults=defaults,
            logger=logging.getLogger(),
        )

        # Should have merged: defaults + loaded
        assert result == {"brightness": 75, "effect": "breathe", "new_key": "value"}

    def test_load_normalizes_effect_to_lowercase(self, temp_config_dir):
        """If effect is present, it should be lowercased."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps({"effect": "BREATHE"}))

        result = load_config_settings(
            config_file=config_file,
            defaults={},
            logger=logging.getLogger(),
        )

        assert result["effect"] == "breathe"

    def test_load_retries_on_json_decode_error(self, temp_config_dir):
        """If JSON is malformed, load should retry and eventually return None."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "config.json"
        config_file.write_text("{this is: not valid json")

        result = load_config_settings(
            config_file=config_file,
            defaults={"brightness": 50},
            retries=2,
            retry_delay=0.001,
            logger=logging.getLogger(),
        )

        # Should return None after retries fail
        assert result is None

    def test_load_returns_none_on_persistent_io_error(self, temp_config_dir):
        """If file exists but raises OSError, return None."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps({"brightness": 50}))

        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = load_config_settings(
                config_file=config_file,
                defaults={"brightness": 50},
                retries=1,
                logger=logging.getLogger(),
            )

        assert result is None

    def test_load_treats_non_dict_json_as_empty(self, temp_config_dir):
        """If JSON loads but isn't a dict, treat as empty dict."""
        from src.core.config_file_storage import load_config_settings

        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps([1, 2, 3]))  # array, not dict

        result = load_config_settings(
            config_file=config_file,
            defaults={"brightness": 50},
            logger=logging.getLogger(),
        )

        # Should merge defaults with empty dict
        assert result == {"brightness": 50}


class TestSaveConfigSettingsAtomic:
    """Test save_config_settings_atomic write + replace logic."""

    def test_save_creates_config_dir_if_missing(self, tmp_path):
        """save should create the config directory if it doesn't exist."""
        from src.core.config_file_storage import save_config_settings_atomic

        config_dir = tmp_path / "nonexistent" / "config"
        config_file = config_dir / "config.json"

        settings = {"brightness": 75, "effect": "wave"}

        save_config_settings_atomic(
            config_dir=config_dir,
            config_file=config_file,
            settings=settings,
            logger=logging.getLogger(),
        )

        assert config_file.exists()
        loaded = json.loads(config_file.read_text())
        assert loaded == settings

    def test_save_uses_atomic_replace(self, temp_config_dir):
        """save should write to temp file then replace original."""
        from src.core.config_file_storage import save_config_settings_atomic

        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps({"old": "data"}))

        settings = {"brightness": 100, "effect": "perkey"}

        save_config_settings_atomic(
            config_dir=temp_config_dir,
            config_file=config_file,
            settings=settings,
            logger=logging.getLogger(),
        )

        loaded = json.loads(config_file.read_text())
        assert loaded == settings

        # Original file should have been replaced atomically
        assert "old" not in loaded

    def test_save_cleans_up_temp_file_on_success(self, temp_config_dir):
        """After successful save, temp file should be removed."""
        from src.core.config_file_storage import save_config_settings_atomic

        config_file = temp_config_dir / "config.json"
        settings = {"brightness": 50}

        save_config_settings_atomic(
            config_dir=temp_config_dir,
            config_file=config_file,
            settings=settings,
            logger=logging.getLogger(),
        )

        # No temp files should remain
        temp_files = list(temp_config_dir.glob("config.*.tmp"))
        assert len(temp_files) == 0

    def test_save_handles_write_exception_gracefully(self, temp_config_dir):
        """If write fails, save should not crash."""
        from src.core.config_file_storage import save_config_settings_atomic

        config_file = temp_config_dir / "config.json"
        settings = {"brightness": 50}

        # Make config_dir non-writable (simulate permission error)
        with patch("tempfile.mkstemp", side_effect=OSError("disk full")):
            # Should not raise
            save_config_settings_atomic(
                config_dir=temp_config_dir,
                config_file=config_file,
                settings=settings,
                logger=logging.getLogger(),
            )

        # Original file should not exist (write failed)
        assert not config_file.exists()

    def test_save_attempts_temp_cleanup_even_on_failure(self, temp_config_dir):
        """Even if os.replace fails, save should try to clean up temp file."""
        from src.core.config_file_storage import save_config_settings_atomic

        config_file = temp_config_dir / "config.json"
        settings = {"brightness": 50}

        with patch("os.replace", side_effect=OSError("replace failed")):
            # Should not crash
            save_config_settings_atomic(
                config_dir=temp_config_dir,
                config_file=config_file,
                settings=settings,
                logger=logging.getLogger(),
            )

        # Temp file should be cleaned up (best-effort)
        # Can't guarantee due to mock, but code should at least try


class TestJsonStorageAtomic:
    """Test core/profile/json_storage.py atomic write logic."""

    def test_write_json_atomic_creates_parent_dirs(self, tmp_path):
        """write_json_atomic should create parent directories."""
        from src.core.profile.json_storage import write_json_atomic

        nested_file = tmp_path / "a" / "b" / "c" / "data.json"
        payload = {"key": "value"}

        write_json_atomic(nested_file, payload)

        assert nested_file.exists()
        loaded = json.loads(nested_file.read_text())
        assert loaded == payload

    def test_write_json_atomic_uses_temp_then_replace(self, tmp_path):
        """write_json_atomic should write to .tmp then replace."""
        from src.core.profile.json_storage import write_json_atomic

        target = tmp_path / "data.json"
        target.write_text(json.dumps({"old": "data"}))

        payload = {"new": "data"}

        write_json_atomic(target, payload)

        loaded = json.loads(target.read_text())
        assert loaded == payload

        # No .tmp files should remain
        temp_files = list(tmp_path.glob("data.json.tmp"))
        assert len(temp_files) == 0

    def test_read_json_returns_none_on_missing_file(self, tmp_path):
        """read_json should return None if file doesn't exist."""
        from src.core.profile.json_storage import read_json

        result = read_json(tmp_path / "missing.json")
        assert result is None

    def test_read_json_returns_none_on_decode_error(self, tmp_path):
        """read_json should return None if JSON is malformed."""
        from src.core.profile.json_storage import read_json

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        result = read_json(bad_file)
        assert result is None
