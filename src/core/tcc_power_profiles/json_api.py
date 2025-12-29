from __future__ import annotations

import json
from typing import Optional

from .busctl import _busctl_call, _parse_busctl_string_reply
from .models import TccProfile


def is_tccd_available() -> bool:
    """Return True if we can talk to the TCC daemon via DBus."""

    # A cheap call; if this fails, nothing else will work.
    return get_profiles_json() is not None


def get_profiles_json() -> Optional[str]:
    stdout = _busctl_call("GetProfilesJSON")
    if stdout is None:
        return None
    return _parse_busctl_string_reply(stdout)


def get_custom_profiles_json() -> Optional[str]:
    stdout = _busctl_call("GetCustomProfilesJSON")
    if stdout is None:
        return None
    return _parse_busctl_string_reply(stdout)


def get_default_values_profile_json() -> Optional[str]:
    stdout = _busctl_call("GetDefaultValuesProfileJSON")
    if stdout is None:
        return None
    return _parse_busctl_string_reply(stdout)


def get_settings_json() -> Optional[str]:
    stdout = _busctl_call("GetSettingsJSON")
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


def _list_profiles_from_json(raw: Optional[str]) -> list[TccProfile]:
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


def list_custom_profiles() -> list[TccProfile]:
    return _list_profiles_from_json(get_custom_profiles_json())
