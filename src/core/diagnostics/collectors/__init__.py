from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .backends import backend_probe_snapshot
from .system import (
    app_snapshot,
    list_module_hints,
    list_platform_hints,
    power_supply_snapshot,
    system_power_mode_snapshot,
    system_snapshot,
)
from ..paths import config_file_path


logger = logging.getLogger(__name__)

_CONFIG_STAT_METADATA_ERRORS = (OSError, OverflowError, TypeError, ValueError)


def _log_snapshot_boundary(message: str, exc: Exception) -> None:
    logger.log(logging.DEBUG, message, exc_info=(type(exc), exc, exc.__traceback__))


def _config_error_text(cfg_path: Path | None, exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON at line {exc.lineno} column {exc.colno}"

    if isinstance(exc, OSError):
        if exc.strerror:
            return exc.strerror
        if exc.errno is not None:
            return f"[Errno {exc.errno}] {type(exc).__name__}"
        return type(exc).__name__

    message = exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""
    if not message:
        return type(exc).__name__
    cfg_path_text = str(cfg_path) if cfg_path is not None else ""
    return message.replace(cfg_path_text, "config.json") if cfg_path_text else message


def config_snapshot() -> dict[str, Any]:
    """Collect a small snapshot of KeyRGB config (best-effort).

    Intentionally avoids dumping large maps (like per-key colors) and avoids
    embedding user-specific paths.
    """

    out: dict[str, Any] = {"present": False}
    cfg_path: Path | None = None
    raw_config = ""

    try:
        cfg_path = config_file_path()
        try:
            st = cfg_path.stat()
            out["mtime"] = int(st.st_mtime)
        except FileNotFoundError:
            return out
        except _CONFIG_STAT_METADATA_ERRORS:
            pass
        out["present"] = True

        raw_config = cfg_path.read_text(encoding="utf-8", errors="ignore")

        data = json.loads(raw_config)
        if not isinstance(data, dict):
            return out

        whitelist = (
            "effect",
            "speed",
            "brightness",
            "color",
            "autostart",
            "os_autostart",
            "power_management_enabled",
            "power_off_on_suspend",
            "power_off_on_lid_close",
            "power_restore_on_resume",
            "power_restore_on_lid_open",
            "battery_saver_enabled",
            "battery_saver_brightness",
            "ac_lighting_enabled",
            "ac_lighting_brightness",
            "battery_lighting_enabled",
            "battery_lighting_brightness",
        )
        settings: dict[str, Any] = {}
        for key in whitelist:
            if key in data:
                settings[key] = data[key]
        if settings:
            out["settings"] = settings

        pk = data.get("per_key_colors")
        if isinstance(pk, dict):
            out["per_key_colors_count"] = len(pk)

        return out
    except json.JSONDecodeError as exc:
        out["error"] = _config_error_text(cfg_path, exc)
        return out
    except OSError as exc:
        out["error"] = _config_error_text(cfg_path, exc)
        return out
    except Exception as exc:  # @quality-exception exception-transparency: config snapshot collection is a best-effort diagnostics boundary
        _log_snapshot_boundary("Failed to collect config snapshot during diagnostics collection", exc)
        out["error"] = _config_error_text(cfg_path, exc)
        return out


__all__ = [
    "app_snapshot",
    "backend_probe_snapshot",
    "config_snapshot",
    "list_module_hints",
    "list_platform_hints",
    "power_supply_snapshot",
    "system_snapshot",
    "system_power_mode_snapshot",
]
