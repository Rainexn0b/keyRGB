from __future__ import annotations

import json
import logging
import os
import random
import tempfile
from typing import Any, Optional

from src.core.logging_utils import log_throttled

from .busctl import _busctl_call, _parse_busctl_bool_reply, _parse_busctl_string_reply
from .json_api import (
    get_active_profile_json,
    get_custom_profiles_json,
    get_default_values_profile_json,
    get_profiles_json,
    get_settings_json,
    is_tccd_available,
    list_custom_profiles,
    list_profiles,
)
from .models import TccProfile, TccProfileWriteError
from .root_apply import _apply_new_profiles_file, _apply_new_settings_file, _run_root_command, _tccd_binary


logger = logging.getLogger(__name__)


def _load_custom_profiles_payload() -> list[dict[str, Any]]:
    raw = get_custom_profiles_json()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise TccProfileWriteError(f"Failed to parse custom profiles JSON from tccd: {exc}")
    if not isinstance(payload, list):
        raise TccProfileWriteError("Custom profiles JSON from tccd is not a list")
    out: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            out.append(item)
    return out


def _load_settings_payload() -> dict[str, Any]:
    raw = get_settings_json()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise TccProfileWriteError(f"Failed to parse settings JSON from tccd: {exc}")
    if not isinstance(payload, dict):
        raise TccProfileWriteError("Settings JSON from tccd is not an object")
    return payload


def _generate_profile_id(existing: set[str]) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    for _ in range(200):
        pid = "".join(random.choice(alphabet) for _ in range(20))
        if pid not in existing:
            return pid
    raise TccProfileWriteError("Failed to generate a unique profile id")


def _unlink_tmp(path: str, *, key: str) -> None:
    try:
        os.unlink(path)
    except OSError as exc:
        log_throttled(
            logger,
            key,
            interval_s=60,
            level=logging.DEBUG,
            msg=f"Failed to remove temp file: {path}",
            exc=exc,
        )


def _write_temp_json(payload: Any, *, prefix: str) -> str:
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        _unlink_tmp(path, key="tcc_power_profiles.write_temp_json.cleanup")
        raise
    return path


def get_custom_profile_payload(profile_id: str) -> Optional[dict[str, Any]]:
    """Return a deep-copied payload dict for a custom profile, or None if not found."""

    if not isinstance(profile_id, str) or not profile_id:
        return None
    for p in _load_custom_profiles_payload():
        if isinstance(p, dict) and p.get("id") == profile_id:
            return json.loads(json.dumps(p))
    return None


def update_custom_profile(profile_id: str, new_payload: dict[str, Any]) -> None:
    """Replace a custom profile payload and persist to tccd.

    The profile id is fixed and cannot be changed by the payload.
    Requires root (pkexec/sudo).
    """

    if not isinstance(profile_id, str) or not profile_id:
        raise TccProfileWriteError("Invalid profile id")
    if not isinstance(new_payload, dict):
        raise TccProfileWriteError("Profile payload must be a JSON object")
    if profile_id.startswith("__legacy_"):
        raise TccProfileWriteError("Legacy profiles cannot be edited")

    custom_profiles = _load_custom_profiles_payload()
    idx = -1
    for i, p in enumerate(custom_profiles):
        if isinstance(p, dict) and p.get("id") == profile_id:
            idx = i
            break
    if idx < 0:
        raise TccProfileWriteError("Profile not found among custom profiles")

    payload = json.loads(json.dumps(new_payload))
    payload["id"] = profile_id

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise TccProfileWriteError("Profile name must be a non-empty string")
    payload["name"] = name.strip()

    custom_profiles[idx] = payload
    tmp = _write_temp_json(custom_profiles, prefix="keyrgb-tcc-profiles-")
    try:
        _apply_new_profiles_file(tmp)
    finally:
        _unlink_tmp(tmp, key="tcc_power_profiles.update_custom_profile.cleanup")


def is_custom_profile_id(profile_id: str) -> bool:
    if not isinstance(profile_id, str) or not profile_id:
        return False
    if profile_id.startswith("__legacy_"):
        return False
    # Custom IDs include __default_custom_profile__ and generated ids.
    return True


def create_custom_profile(name: str) -> str:
    """Create a new custom profile (persisted in tccd).

    Requires root (pkexec/sudo), because it calls the tccd helper.
    Returns the new profile id.
    """

    name = str(name).strip()
    if not name:
        raise TccProfileWriteError("Profile name cannot be empty")

    custom_profiles = _load_custom_profiles_payload()
    existing_ids = {str(p.get("id")) for p in custom_profiles if isinstance(p, dict) and isinstance(p.get("id"), str)}

    base_raw = get_default_values_profile_json()
    if not base_raw:
        raise TccProfileWriteError("Failed to fetch default values profile from tccd")
    try:
        base_profile = json.loads(base_raw)
    except Exception as exc:
        raise TccProfileWriteError(f"Failed to parse default values profile JSON: {exc}")
    if not isinstance(base_profile, dict):
        raise TccProfileWriteError("Default values profile JSON is not an object")

    new_id = _generate_profile_id(existing_ids)
    base_profile["id"] = new_id
    base_profile["name"] = name
    base_profile.setdefault("description", "Edit profile to change behaviour")

    custom_profiles.append(base_profile)

    tmp = _write_temp_json(custom_profiles, prefix="keyrgb-tcc-profiles-")
    try:
        _apply_new_profiles_file(tmp)
    finally:
        _unlink_tmp(tmp, key="tcc_power_profiles.create_custom_profile.cleanup")

    return new_id


def duplicate_custom_profile(source_profile_id: str, new_name: str) -> str:
    new_name = str(new_name).strip()
    if not new_name:
        raise TccProfileWriteError("Profile name cannot be empty")

    custom_profiles = _load_custom_profiles_payload()
    source: Optional[dict[str, Any]] = None
    for p in custom_profiles:
        if isinstance(p, dict) and p.get("id") == source_profile_id:
            source = p
            break

    if source is None:
        raise TccProfileWriteError("Can only duplicate custom profiles")

    existing_ids = {str(p.get("id")) for p in custom_profiles if isinstance(p, dict) and isinstance(p.get("id"), str)}
    new_id = _generate_profile_id(existing_ids)

    clone = json.loads(json.dumps(source))
    clone["id"] = new_id
    clone["name"] = new_name

    custom_profiles.append(clone)
    tmp = _write_temp_json(custom_profiles, prefix="keyrgb-tcc-profiles-")
    try:
        _apply_new_profiles_file(tmp)
    finally:
        _unlink_tmp(tmp, key="tcc_power_profiles.duplicate_custom_profile.cleanup")

    return new_id


def rename_custom_profile(profile_id: str, new_name: str) -> None:
    new_name = str(new_name).strip()
    if not new_name:
        raise TccProfileWriteError("Profile name cannot be empty")
    if profile_id.startswith("__") and profile_id != "__default_custom_profile__":
        raise TccProfileWriteError("Built-in profiles cannot be renamed")

    custom_profiles = _load_custom_profiles_payload()
    updated = False
    for p in custom_profiles:
        if isinstance(p, dict) and p.get("id") == profile_id:
            p["name"] = new_name
            updated = True
            break
    if not updated:
        raise TccProfileWriteError("Profile not found among custom profiles")

    tmp = _write_temp_json(custom_profiles, prefix="keyrgb-tcc-profiles-")
    try:
        _apply_new_profiles_file(tmp)
    finally:
        _unlink_tmp(tmp, key="tcc_power_profiles.rename_custom_profile.cleanup")


def delete_custom_profile(profile_id: str) -> None:
    if profile_id == "__default_custom_profile__":
        raise TccProfileWriteError("The default custom profile cannot be deleted")
    if profile_id.startswith("__"):
        raise TccProfileWriteError("Built-in profiles cannot be deleted")

    custom_profiles = _load_custom_profiles_payload()
    new_profiles = [p for p in custom_profiles if not (isinstance(p, dict) and p.get("id") == profile_id)]
    if len(new_profiles) == len(custom_profiles):
        raise TccProfileWriteError("Profile not found among custom profiles")

    # Update state assignments if they referenced the deleted profile.
    settings = _load_settings_payload()
    state_map = settings.get("stateMap")
    if isinstance(state_map, dict):
        changed = False
        for k, v in list(state_map.items()):
            if v == profile_id:
                state_map[k] = "__default_custom_profile__"
                changed = True
        if changed:
            settings["stateMap"] = state_map

    tmp_profiles = _write_temp_json(new_profiles, prefix="keyrgb-tcc-profiles-")
    tmp_settings: Optional[str] = None
    try:
        _apply_new_profiles_file(tmp_profiles)
        if isinstance(settings, dict) and isinstance(settings.get("stateMap"), dict):
            tmp_settings = _write_temp_json(settings, prefix="keyrgb-tcc-settings-")
            _apply_new_settings_file(tmp_settings)
    finally:
        for p in [tmp_profiles, tmp_settings]:
            if p:
                _unlink_tmp(p, key="tcc_power_profiles.delete_custom_profile.cleanup")


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
