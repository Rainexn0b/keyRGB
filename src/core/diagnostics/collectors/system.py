from __future__ import annotations

import logging
import re
from importlib import metadata
from pathlib import Path
from typing import Any

from src.core.runtime.imports import repo_root_from

from ..io import read_kv_file, read_text


logger = logging.getLogger(__name__)

_FS_SNAPSHOT_ERRORS = (OSError,)
_METADATA_LOOKUP_ERRORS = (metadata.PackageNotFoundError,)
_SYSTEM_INFO_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


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
        for child in sorted(root.iterdir(), key=lambda path: path.name):
            name = child.name.lower()
            if any(pattern in name for pattern in patterns):
                candidates.append(child.name)
        return candidates[:80]
    except _FS_SNAPSHOT_ERRORS:
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
            name = (line.split() or [""])[0]
            if name and keep.search(name):
                out.append(name)
        seen: set[str] = set()
        unique: list[str] = []
        for module_name in out:
            if module_name in seen:
                continue
            seen.add(module_name)
            unique.append(module_name)
        return unique[:120]
    except _FS_SNAPSHOT_ERRORS:
        return []


def power_supply_snapshot() -> dict[str, Any]:
    """Collect a tiny power-supply snapshot (read-only, best-effort)."""

    root = Path("/sys/class/power_supply")
    out: dict[str, Any] = {}
    try:
        if not root.exists():
            return {}

        for device in sorted(root.iterdir(), key=lambda path: path.name):
            if not device.is_dir():
                continue

            entry: dict[str, str] = {}
            for key in (
                "type",
                "status",
                "online",
                "capacity",
                "charge_now",
                "energy_now",
            ):
                value = read_text(device / key)
                if value is not None and value != "":
                    entry[key] = value

            if entry:
                out[device.name] = entry

        return out
    except _FS_SNAPSHOT_ERRORS:
        return {}


def _repo_version_text(anchor: str | Path) -> str | None:
    """Best-effort: if running from a source checkout, read version from pyproject.toml.

    Avoids `tomllib` so it works on older runtimes.
    """

    try:
        root = repo_root_from(anchor)
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return None

        in_project = False
        version_re = re.compile(r'^\s*version\s*=\s*"([^"]+)"\s*$')

        for raw_line in pyproject.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if line == "[project]":
                in_project = True
                continue
            if in_project and line.startswith("[") and line.endswith("]"):
                break
            if not in_project:
                continue

            line = raw_line.split("#", 1)[0].strip()
            match = version_re.match(line)
            if match:
                return match.group(1).strip()

        return None
    except _FS_SNAPSHOT_ERRORS:
        return None


def app_snapshot() -> dict[str, Any]:
    app: dict[str, Any] = {}

    repo_version = _repo_version_text(__file__)
    if repo_version:
        app["version"] = repo_version
        app["version_source"] = "pyproject"

        for dist_name in ("keyrgb", "Keyrgb", "KeyRGB"):
            try:
                app["dist_name"] = dist_name
                app["dist_version"] = metadata.version(dist_name)
                break
            except _METADATA_LOOKUP_ERRORS:
                continue
    else:
        for dist_name in ("keyrgb", "Keyrgb", "KeyRGB"):
            try:
                app["version"] = metadata.version(dist_name)
                app["dist"] = dist_name
                app["version_source"] = "dist"
                break
            except _METADATA_LOOKUP_ERRORS:
                continue

    return app


def system_snapshot() -> dict[str, Any]:
    import platform
    import sys

    system: dict[str, Any] = {}
    try:
        uname = platform.uname()
        system["kernel_release"] = uname.release
        system["machine"] = uname.machine
    except _SYSTEM_INFO_ERRORS:
        pass
    try:
        system["python"] = sys.version.split()[0]
    except _SYSTEM_INFO_ERRORS:
        pass

    os_release = read_kv_file(Path("/etc/os-release"))
    if os_release:
        keep_keys = ("NAME", "PRETTY_NAME", "ID", "VERSION_ID", "VARIANT_ID")
        system["os_release"] = {key: os_release[key] for key in keep_keys if key in os_release}

    return system


def system_power_mode_snapshot() -> dict[str, Any]:
    """Collect a tiny snapshot of KeyRGB's lightweight system power mode.

    Read-only and best-effort: reads sysfs cpufreq policies and helper presence.
    """

    try:
        from src.core.power.system import get_status

        status = get_status()
        return {
            "supported": bool(status.supported),
            "mode": str(status.mode.value),
            "reason": str(status.reason),
            "identifiers": dict(status.identifiers or {}),
        }
    except Exception as exc:  # @quality-exception exception-transparency: system power mode collection is an arbitrary runtime subsystem boundary; returns a safe fallback dict on any failure
        logger.log(logging.DEBUG, "Failed to collect system power mode diagnostics", exc_info=True)
        return {
            "supported": False,
            "mode": "unknown",
            "reason": "error",
            "error": str(exc),
        }
