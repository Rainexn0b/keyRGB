from __future__ import annotations

import json
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src.core.tcc_power_profiles as tcc_power_profiles
from src.core.tcc_power_profiles.busctl import (
    _parse_busctl_string_reply,
    _parse_busctl_bool_reply,
)


@pytest.mark.parametrize(
    "stdout, expected",
    [
        ('s "{\\"a\\": 1}"', '{"a": 1}'),
        ('s "hello"', "hello"),
        ("", None),
        ("b true", None),
    ],
)
def test_parse_busctl_string_reply(stdout: str, expected: str | None) -> None:
    assert _parse_busctl_string_reply(stdout) == expected


@pytest.mark.parametrize(
    "stdout, expected",
    [
        ("b true", True),
        ("b false", False),
        ("b 1", True),
        ("b 0", False),
        ('s "x"', None),
        ("", None),
    ],
)
def test_parse_busctl_bool_reply(stdout: str, expected: bool | None) -> None:
    assert _parse_busctl_bool_reply(stdout) == expected


def test_update_custom_profile_preserves_id_and_strips_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, object] = {}

    def fake_load_custom_profiles_payload():
        return [
            {"id": "abc", "name": "Old", "x": 1},
            {"id": "def", "name": "Other"},
        ]

    def fake_write_temp_json(payload, *, prefix: str):
        # validate payload is JSON-serializable and capture it
        json.dumps(payload)
        stored["payload"] = payload
        stored["prefix"] = prefix
        return "/tmp/fake.json"

    def fake_apply_new_profiles_file(path: str) -> None:
        stored["applied"] = path

    monkeypatch.setattr(
        tcc_power_profiles,
        "_load_custom_profiles_payload",
        fake_load_custom_profiles_payload,
    )
    monkeypatch.setattr(tcc_power_profiles, "_write_temp_json", fake_write_temp_json)
    monkeypatch.setattr(tcc_power_profiles, "_apply_new_profiles_file", fake_apply_new_profiles_file)

    tcc_power_profiles.update_custom_profile("abc", {"id": "zzz", "name": "  New Name  ", "x": 2})

    assert stored["applied"] == "/tmp/fake.json"
    payload = stored["payload"]
    assert isinstance(payload, list)
    # First profile updated
    assert payload[0]["id"] == "abc"
    assert payload[0]["name"] == "New Name"
    assert payload[0]["x"] == 2
    # Second profile unchanged
    assert payload[1]["id"] == "def"


def test_update_custom_profile_rejects_empty_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tcc_power_profiles,
        "_load_custom_profiles_payload",
        lambda: [{"id": "abc", "name": "Old"}],
    )

    with pytest.raises(tcc_power_profiles.TccProfileWriteError):
        tcc_power_profiles.update_custom_profile("abc", {"name": "   "})
