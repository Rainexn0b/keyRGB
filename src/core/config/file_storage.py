from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


_CONFIG_LOAD_TERMINAL_ERRORS = (OSError, RecursionError, TypeError, ValueError)
_CONFIG_SAVE_ERRORS = (OSError, RecursionError, TypeError, ValueError)


def _log_warning_with_traceback(logger, message: str, exc: Exception) -> None:
    logger.warning(message, exc, exc_info=(type(exc), exc, exc.__traceback__))


def load_config_settings(
    *,
    config_file: Path,
    defaults: dict[str, Any],
    retries: int = 3,
    retry_delay: float = 0.02,
    logger,
) -> dict[str, Any] | None:
    """Load config JSON with retries for transient partial writes.

    Returns a merged dict of `{**defaults, **loaded}` when successful.
    Returns a copy of `defaults` when the file does not exist.
    Returns None when loading fails after retries.
    """

    if not config_file.exists():
        return dict(defaults)

    last_error: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                loaded = {}

            if "effect" in loaded and isinstance(loaded["effect"], str):
                loaded["effect"] = loaded["effect"].lower()

            # Removed older software effects still normalize to a safe supported mode
            # instead of surfacing an unknown-effect failure during startup.
            older_effect_name = loaded.get("effect")
            if older_effect_name in {"static", "pulse"}:
                loaded["effect"] = "none"
            elif older_effect_name in {"breathing_sw", "fire", "random", "rain"}:
                loaded["effect"] = "none"

            if "return_effect_after_effect" in loaded and isinstance(loaded["return_effect_after_effect"], str):
                loaded["return_effect_after_effect"] = loaded["return_effect_after_effect"].lower()

            return {**defaults, **loaded}
        except json.JSONDecodeError as e:
            last_error = e
            time.sleep(retry_delay)
        except _CONFIG_LOAD_TERMINAL_ERRORS as e:
            last_error = e
            break

    if last_error is not None:
        _log_warning_with_traceback(logger, "Failed to load config: %s", last_error)
    return None


def save_config_settings_atomic(*, config_dir: Path, config_file: Path, settings: dict[str, Any], logger) -> None:
    """Save config JSON atomically (write temp file then replace)."""

    try:
        config_dir.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=str(config_dir))
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, config_file)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError as exc:
                logger.debug("Failed to remove temp config file %s: %s", tmp_path, exc)

    except _CONFIG_SAVE_ERRORS as e:
        _log_warning_with_traceback(logger, "Failed to save config: %s", e)
