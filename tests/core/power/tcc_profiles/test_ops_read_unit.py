from __future__ import annotations

import json

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.power.tcc_profiles.models import TccProfile
from src.core.power.tcc_profiles.ops_read import get_active_profile, set_temp_profile_by_id


def test_get_active_profile_returns_none_for_empty_raw_payload() -> None:
    assert get_active_profile(get_active_profile_json_fn=lambda: "") is None


def test_get_active_profile_returns_none_for_invalid_json() -> None:
    assert get_active_profile(get_active_profile_json_fn=lambda: "{") is None


def test_get_active_profile_returns_none_for_non_dict_payload() -> None:
    assert get_active_profile(get_active_profile_json_fn=lambda: "[]") is None


def test_get_active_profile_returns_none_for_missing_or_invalid_id_name_types() -> None:
    assert get_active_profile(get_active_profile_json_fn=lambda: json.dumps({"name": "Balanced"})) is None
    assert get_active_profile(get_active_profile_json_fn=lambda: json.dumps({"id": "balanced"})) is None
    assert get_active_profile(
        get_active_profile_json_fn=lambda: json.dumps({"id": 123, "name": "Balanced"})
    ) is None
    assert get_active_profile(
        get_active_profile_json_fn=lambda: json.dumps({"id": "balanced", "name": 123})
    ) is None


def test_get_active_profile_maps_none_description_to_empty_string() -> None:
    raw = json.dumps({"id": "balanced", "name": "Balanced", "description": None})

    assert get_active_profile(get_active_profile_json_fn=lambda: raw) == TccProfile(
        id="balanced",
        name="Balanced",
        description="",
    )


def test_get_active_profile_coerces_description_to_string() -> None:
    raw = json.dumps({"id": "balanced", "name": "Balanced", "description": 123})

    assert get_active_profile(get_active_profile_json_fn=lambda: raw) == TccProfile(
        id="balanced",
        name="Balanced",
        description="123",
    )


def test_set_temp_profile_by_id_rejects_invalid_profile_id_values() -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_busctl_call(method: str, sig: str, profile_id: str):
        calls.append((method, sig, profile_id))
        return "b true"

    assert set_temp_profile_by_id("", busctl_call=fake_busctl_call) is False
    assert set_temp_profile_by_id(None, busctl_call=fake_busctl_call) is False  # type: ignore[arg-type]
    assert calls == []


def test_set_temp_profile_by_id_returns_false_when_busctl_returns_none() -> None:
    assert (
        set_temp_profile_by_id(
            "balanced",
            busctl_call=lambda method, sig, profile_id: None,
            parse_bool_reply=lambda stdout: True,
        )
        is False
    )


def test_set_temp_profile_by_id_returns_false_when_bool_reply_is_false() -> None:
    assert (
        set_temp_profile_by_id(
            "balanced",
            busctl_call=lambda method, sig, profile_id: "b false",
            parse_bool_reply=lambda stdout: False,
        )
        is False
    )


def test_set_temp_profile_by_id_returns_true_when_bool_reply_is_true() -> None:
    assert (
        set_temp_profile_by_id(
            "balanced",
            busctl_call=lambda method, sig, profile_id: "b true",
            parse_bool_reply=lambda stdout: True,
        )
        is True
    )