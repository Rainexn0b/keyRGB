from __future__ import annotations

from typing import Any, Optional

from .busctl import _busctl_call, _parse_busctl_bool_reply, _parse_busctl_string_reply
from . import ops_read as _ops_read
from . import ops_write as _ops_write
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
from .root_apply import (
    _apply_new_profiles_file,
    _apply_new_settings_file,
    _run_root_command,
    _tccd_binary,
)

_load_custom_profiles_payload = _ops_write._load_custom_profiles_payload
_load_settings_payload = _ops_write._load_settings_payload
_generate_profile_id = _ops_write._generate_profile_id
_unlink_tmp = _ops_write._unlink_tmp
_write_temp_json = _ops_write._write_temp_json

__all__ = [
    "TccProfile",
    "TccProfileWriteError",
    "create_custom_profile",
    "delete_custom_profile",
    "duplicate_custom_profile",
    "get_active_profile",
    "get_active_profile_json",
    "get_custom_profile_payload",
    "get_custom_profiles_json",
    "get_default_values_profile_json",
    "get_profiles_json",
    "get_settings_json",
    "is_custom_profile_id",
    "is_tccd_available",
    "list_custom_profiles",
    "list_profiles",
    "rename_custom_profile",
    "set_temp_profile_by_id",
    "update_custom_profile",
    # Intentionally re-export internal helpers used by the tray UI and tests.
    "_apply_new_profiles_file",
    "_apply_new_settings_file",
    "_busctl_call",
    "_parse_busctl_bool_reply",
    "_parse_busctl_string_reply",
    "_run_root_command",
    "_tccd_binary",
]


def get_custom_profile_payload(profile_id: str) -> Optional[dict[str, Any]]:
    """Return a deep-copied payload dict for a custom profile, or None if not found."""

    return _ops_write.get_custom_profile_payload(
        profile_id,
        load_custom_profiles_payload=_load_custom_profiles_payload,
    )


def update_custom_profile(profile_id: str, new_payload: dict[str, Any]) -> None:
    """Replace a custom profile payload and persist to tccd.

    The profile id is fixed and cannot be changed by the payload.
    Requires root (pkexec/sudo).
    """

    return _ops_write.update_custom_profile(
        profile_id,
        new_payload,
        load_custom_profiles_payload=_load_custom_profiles_payload,
        write_temp_json=_write_temp_json,
        apply_new_profiles_file=_apply_new_profiles_file,
        unlink_tmp=_unlink_tmp,
    )


def is_custom_profile_id(profile_id: str) -> bool:
    return _ops_write.is_custom_profile_id(profile_id)


def create_custom_profile(name: str) -> str:
    """Create a new custom profile (persisted in tccd).

    Requires root (pkexec/sudo), because it calls the tccd helper.
    Returns the new profile id.
    """

    return _ops_write.create_custom_profile(
        name,
        load_custom_profiles_payload=_load_custom_profiles_payload,
        get_default_values_profile_json_fn=get_default_values_profile_json,
        generate_profile_id=_generate_profile_id,
        write_temp_json=_write_temp_json,
        apply_new_profiles_file=_apply_new_profiles_file,
        unlink_tmp=_unlink_tmp,
    )


def duplicate_custom_profile(source_profile_id: str, new_name: str) -> str:
    return _ops_write.duplicate_custom_profile(
        source_profile_id,
        new_name,
        load_custom_profiles_payload=_load_custom_profiles_payload,
        generate_profile_id=_generate_profile_id,
        write_temp_json=_write_temp_json,
        apply_new_profiles_file=_apply_new_profiles_file,
        unlink_tmp=_unlink_tmp,
    )


def rename_custom_profile(profile_id: str, new_name: str) -> None:
    return _ops_write.rename_custom_profile(
        profile_id,
        new_name,
        load_custom_profiles_payload=_load_custom_profiles_payload,
        write_temp_json=_write_temp_json,
        apply_new_profiles_file=_apply_new_profiles_file,
        unlink_tmp=_unlink_tmp,
    )


def delete_custom_profile(profile_id: str) -> None:
    return _ops_write.delete_custom_profile(
        profile_id,
        load_custom_profiles_payload=_load_custom_profiles_payload,
        load_settings_payload=_load_settings_payload,
        write_temp_json=_write_temp_json,
        apply_new_profiles_file=_apply_new_profiles_file,
        apply_new_settings_file=_apply_new_settings_file,
        unlink_tmp=_unlink_tmp,
    )


def get_active_profile() -> Optional[TccProfile]:
    return _ops_read.get_active_profile(get_active_profile_json_fn=get_active_profile_json)


def set_temp_profile_by_id(profile_id: str) -> bool:
    """Request switching to a profile (temporary) via TCC daemon."""
    return _ops_read.set_temp_profile_by_id(
        profile_id,
        busctl_call=_busctl_call,
        parse_bool_reply=_parse_busctl_bool_reply,
    )
