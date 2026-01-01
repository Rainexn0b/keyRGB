from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .collectors_backends import backend_probe_snapshot
from .collectors_system import (
    app_snapshot,
    list_module_hints,
    list_platform_hints,
    power_supply_snapshot,
    system_snapshot,
)
from .paths import config_file_path


def config_snapshot() -> dict[str, Any]:
    """Collect a small snapshot of KeyRGB config (best-effort).

    Intentionally avoids dumping large maps (like per-key colors) and avoids
    embedding user-specific paths.
    """

    cfg_path = config_file_path()
    out: dict[str, Any] = {"present": False}

    try:
        if not cfg_path.exists():
            return out
        out["present"] = True
        try:
            st = cfg_path.stat()
            out["mtime"] = int(st.st_mtime)
        except Exception:
            pass

        data = json.loads(cfg_path.read_text(encoding="utf-8", errors="ignore"))
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
        for k in whitelist:
            if k in data:
                settings[k] = data[k]
        if settings:
            out["settings"] = settings

        pk = data.get("per_key_colors")
        if isinstance(pk, dict):
            out["per_key_colors_count"] = len(pk)

        return out
    except Exception as exc:
        out["error"] = str(exc)
        return out


__all__ = [
    "app_snapshot",
    "backend_probe_snapshot",
    "config_snapshot",
    "list_module_hints",
    "list_platform_hints",
    "power_supply_snapshot",
    "system_snapshot",
]
