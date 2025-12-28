from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TccProfile:
    id: str
    name: str
    description: str = ""


_TCCD_BUS_NAME = "com.tuxedocomputers.tccd"
_TCCD_OBJECT_PATH = "/com/tuxedocomputers/tccd"
_TCCD_INTERFACE = "com.tuxedocomputers.tccd"


def _busctl_call(*args: str) -> Optional[str]:
    """Call busctl and return stdout on success.

    Uses system bus because TCC daemon is system service.
    """

    cmd = [
        "busctl",
        "--system",
        "call",
        _TCCD_BUS_NAME,
        _TCCD_OBJECT_PATH,
        _TCCD_INTERFACE,
        *args,
    ]

    try:
        cp = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return None

    if cp.returncode != 0:
        return None

    return cp.stdout.strip()


def _parse_busctl_string_reply(stdout: str) -> Optional[str]:
    """Parse busctl output for methods that return a single string.

    Example output: `s "{...}"`
    """

    if not stdout:
        return None

    # busctl formats as: <type> <value>
    # for strings: s "..."
    parts = stdout.split(" ", 1)
    if len(parts) != 2:
        return None

    sig, rest = parts
    if sig != "s":
        return None

    rest = rest.strip()
    if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
        rest = rest[1:-1]

    # busctl keeps C-style escapes; json.loads handles standard escapes.
    try:
        return bytes(rest, "utf-8").decode("unicode_escape")
    except Exception:
        return rest


def _parse_busctl_bool_reply(stdout: str) -> Optional[bool]:
    if not stdout:
        return None
    parts = stdout.split(" ", 1)
    if len(parts) != 2:
        return None
    sig, rest = parts
    if sig != "b":
        return None
    rest = rest.strip().lower()
    if rest in ("true", "1"):
        return True
    if rest in ("false", "0"):
        return False
    return None


def is_tccd_available() -> bool:
    """Return True if we can talk to the TCC daemon via DBus."""

    # A cheap call; if this fails, nothing else will work.
    return get_profiles_json() is not None


def get_profiles_json() -> Optional[str]:
    stdout = _busctl_call("GetProfilesJSON")
    if stdout is None:
        return None
    return _parse_busctl_string_reply(stdout)


def get_active_profile_json() -> Optional[str]:
    stdout = _busctl_call("GetActiveProfileJSON")
    if stdout is None:
        return None
    return _parse_busctl_string_reply(stdout)


def list_profiles() -> list[TccProfile]:
    raw = get_profiles_json()
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    out: list[TccProfile] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        name = item.get("name")
        if not isinstance(pid, str) or not isinstance(name, str):
            continue
        desc = item.get("description")
        out.append(TccProfile(id=pid, name=name, description=str(desc) if desc is not None else ""))

    return out


def get_active_profile() -> Optional[TccProfile]:
    raw = get_active_profile_json()
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    pid = payload.get("id")
    name = payload.get("name")
    if not isinstance(pid, str) or not isinstance(name, str):
        return None

    desc = payload.get("description")
    return TccProfile(id=pid, name=name, description=str(desc) if desc is not None else "")


def set_temp_profile_by_id(profile_id: str) -> bool:
    """Request switching to a profile (temporary) via TCC daemon."""

    if not isinstance(profile_id, str) or not profile_id:
        return False

    stdout = _busctl_call("SetTempProfileById", "s", profile_id)
    if stdout is None:
        return False

    result = _parse_busctl_bool_reply(stdout)
    return bool(result)
