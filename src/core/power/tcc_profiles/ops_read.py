from __future__ import annotations

import json
from typing import Optional

from .busctl import _busctl_call, _parse_busctl_bool_reply
from .json_api import get_active_profile_json
from .models import TccProfile


def get_active_profile(*, get_active_profile_json_fn=get_active_profile_json) -> Optional[TccProfile]:
    raw = get_active_profile_json_fn()
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


def set_temp_profile_by_id(
    profile_id: str,
    *,
    busctl_call=_busctl_call,
    parse_bool_reply=_parse_busctl_bool_reply,
) -> bool:
    """Request switching to a profile (temporary) via TCC daemon."""

    if not isinstance(profile_id, str) or not profile_id:
        return False

    stdout = busctl_call("SetTempProfileById", "s", profile_id)
    if stdout is None:
        return False

    result = parse_bool_reply(stdout)
    return bool(result)
