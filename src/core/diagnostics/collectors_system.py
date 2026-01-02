from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path
from typing import Any

from .io import read_kv_file, read_text


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


def system_power_mode_snapshot() -> dict[str, Any]:
    """Collect a tiny snapshot of KeyRGB's lightweight system power mode.

    Read-only and best-effort: reads sysfs cpufreq policies and helper presence.
    """

    try:
        from src.core.system_power import get_status

        st = get_status()
        return {
            "supported": bool(st.supported),
            "mode": str(st.mode.value),
            "reason": str(st.reason),
            "identifiers": dict(st.identifiers or {}),
        }
    except Exception as exc:
        return {"supported": False, "mode": "unknown", "reason": "error", "error": str(exc)}
