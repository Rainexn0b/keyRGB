from __future__ import annotations

import json
import os
import re
from importlib import metadata
from pathlib import Path
from typing import Any

from .io import read_kv_file, read_text
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


def list_platform_hints() -> list[str]:
    """Return a small list of platform device names hinting at laptop vendors."""

    candidates: list[str] = []
    root = Path("/sys/bus/platform/devices")
    patterns = (
        "tuxedo",
        "tongfang",
        "clevo",
        "ite",
        "wmi",
        "asus",
        "dell",
        "thinkpad",
        "msi",
        "acer",
        "hp",
        "lenovo",
    )

    try:
        if not root.exists():
            return []
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            name = child.name.lower()
            if any(p in name for p in patterns):
                candidates.append(child.name)
        return candidates[:80]
    except Exception:
        return []


def list_module_hints() -> list[str]:
    """Return a small list of loaded kernel modules relevant to keyboard backlight support."""

    modules_path = Path("/proc/modules")
    keep = re.compile(r"(tuxedo|clevo|tongfang|ite|i8042|atkbd|hid|hid_.*|wmi|acpi)", re.IGNORECASE)
    out: list[str] = []
    try:
        if not modules_path.exists():
            return []
        for line in modules_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            # Format: name size use_count deps state address
            name = (line.split() or [""])[0]
            if name and keep.search(name):
                out.append(name)
        # Preserve order, unique.
        seen: set[str] = set()
        uniq: list[str] = []
        for m in out:
            if m in seen:
                continue
            seen.add(m)
            uniq.append(m)
        return uniq[:120]
    except Exception:
        return []


def power_supply_snapshot() -> dict[str, Any]:
    """Collect a tiny power-supply snapshot (read-only, best-effort)."""

    root = Path("/sys/class/power_supply")
    out: dict[str, Any] = {}
    try:
        if not root.exists():
            return {}

        for dev in sorted(root.iterdir(), key=lambda p: p.name):
            if not dev.is_dir():
                continue

            entry: dict[str, str] = {}
            for key in ("type", "status", "online", "capacity", "charge_now", "energy_now"):
                val = read_text(dev / key)
                if val is not None and val != "":
                    entry[key] = val

            if entry:
                out[dev.name] = entry

        return out
    except Exception:
        return {}


def backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort)."""

    try:
        from .backends.registry import iter_backends, select_backend
    except Exception:
        return {}

    probes: list[dict[str, Any]] = []
    for backend in iter_backends():
        try:
            probe_fn = getattr(backend, "probe", None)
            if callable(probe_fn):
                result = probe_fn()
                available = bool(getattr(result, "available", False))
                reason = str(getattr(result, "reason", ""))
                confidence = int(getattr(result, "confidence", 0) or 0)
                identifiers = getattr(result, "identifiers", None)
            else:
                available = bool(backend.is_available())
                reason = "is_available"
                confidence = 50 if available else 0
                identifiers = None
        except Exception as exc:
            available = False
            reason = f"probe exception: {exc}"
            confidence = 0
            identifiers = None

        entry: dict[str, Any] = {
            "name": getattr(backend, "name", backend.__class__.__name__),
            "available": available,
            "confidence": confidence,
            "reason": reason,
        }
        if identifiers:
            entry["identifiers"] = dict(identifiers)
        probes.append(entry)

    selected = None
    try:
        selected_backend = select_backend()
        selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception:
        selected = None

    return {
        "selected": selected,
        "requested": (os.environ.get("KEYRGB_BACKEND") or "auto"),
        "probes": probes,
    }


def app_snapshot() -> dict[str, Any]:
    app: dict[str, Any] = {}

    # Best-effort version reporting. Distribution name may vary, so try a couple.
    for dist_name in ("keyrgb", "Keyrgb", "KeyRGB"):
        try:
            app["version"] = metadata.version(dist_name)
            app["dist"] = dist_name
            break
        except Exception:
            continue

    # Optional helper library used on some hardware.
    for dist_name in ("ite8291r3-ctl", "ite8291r3_ctl"):
        try:
            app["ite8291r3_ctl_version"] = metadata.version(dist_name)
            break
        except Exception:
            continue

    return app


def system_snapshot() -> dict[str, Any]:
    # Imported lazily to keep dependency surface minimal.
    import platform
    import sys

    system: dict[str, Any] = {}
    try:
        u = platform.uname()
        system["kernel_release"] = u.release
        system["machine"] = u.machine
    except Exception:
        pass
    try:
        system["python"] = sys.version.split()[0]
    except Exception:
        pass

    os_release = read_kv_file(Path("/etc/os-release"))
    if os_release:
        # Keep only common, stable keys.
        keep_keys = ("NAME", "PRETTY_NAME", "ID", "VERSION_ID", "VARIANT_ID")
        system["os_release"] = {k: os_release[k] for k in keep_keys if k in os_release}

    return system
