"""Unit contracts for KEYRGB_EMULATE parsing, presets, and fail-closed rules."""

from __future__ import annotations

import pytest

from keyrgb.core.backends.emulation import (
    EMULATE_ENVIRONMENT_VARIABLE,
    EmulationError,
    get_emulation_spec,
    parse_emulate_spec,
)
from keyrgb.core.secondary_device_runtime import SIMULATION_ENVIRONMENT_VARIABLE


@pytest.fixture(autouse=True)
def _clear_emulation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EMULATE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(SIMULATION_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)


def test_empty_or_unset_disables_emulation() -> None:
    assert parse_emulate_spec(None) is None
    assert parse_emulate_spec("") is None
    assert parse_emulate_spec("   ") is None
    assert get_emulation_spec() is None


def test_parses_canonical_names_and_aliases() -> None:
    spec = parse_emulate_spec("ite8291-zones, ite8291_none_chassis_lightbar_tongfang")
    assert spec is not None
    assert spec.primary == "ite8291_zones_clevo"
    assert spec.auxiliary == ("ite8291_none_chassis_lightbar_tongfang",)
    assert spec.all_auxiliary is False
    assert spec.source == "emulate"


def test_preset_beast_x30_expands() -> None:
    spec = parse_emulate_spec("preset:beast-x30")
    assert spec is not None
    assert spec.preset == "beast-x30"
    assert spec.primary == "ite8291_zones_clevo"
    assert spec.auxiliary == ("ite8291_none_chassis_lightbar_tongfang",)
    assert spec.names == (
        "ite8291_zones_clevo",
        "ite8291_none_chassis_lightbar_tongfang",
    )


def test_preset_legion_gen10_is_primary_only() -> None:
    spec = parse_emulate_spec("preset:legion-gen10")
    assert spec is not None
    assert spec.primary == "ite8258_perkey_chassis"
    assert spec.auxiliary == ()


def test_unknown_name_and_preset_fail_closed() -> None:
    with pytest.raises(EmulationError, match="Unknown backend name"):
        parse_emulate_spec("not-a-backend")
    with pytest.raises(EmulationError, match="Unknown KEYRGB_EMULATE preset"):
        parse_emulate_spec("preset:does-not-exist")


def test_two_primaries_fail_closed() -> None:
    with pytest.raises(EmulationError, match="at most one PRIMARY"):
        parse_emulate_spec("ite8291_zones_clevo,ite8258_perkey_chassis")


def test_usb_identity_conflict_fails_closed() -> None:
    with pytest.raises(EmulationError, match="conflicting USB-identity"):
        parse_emulate_spec("ite8291r3_perkey,ite8291_perkey")


def test_virtual_child_without_parent_fails_closed() -> None:
    with pytest.raises(EmulationError, match="requires parent PRIMARY"):
        parse_emulate_spec("ite8258-chassis-logo")


def test_star_must_be_sole_token() -> None:
    with pytest.raises(EmulationError, match="must be the only"):
        parse_emulate_spec("*,ite8291_zones_clevo")


def test_legacy_secondary_flag_maps_to_all_auxiliary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    spec = get_emulation_spec()
    assert spec is not None
    assert spec.all_auxiliary is True
    assert spec.primary is None
    assert spec.source == "legacy_secondary_simulate"


def test_emulate_env_wins_over_legacy_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_none_chassis_lightbar_tongfang")
    spec = get_emulation_spec()
    assert spec is not None
    assert spec.source == "emulate"
    assert spec.primary is None
    assert spec.auxiliary == ("ite8291_none_chassis_lightbar_tongfang",)


def test_perkey_plus_clevo_lightbar_classifies_lightbar_as_auxiliary() -> None:
    spec = parse_emulate_spec("preset:perkey-clevo-bar")
    assert spec is not None
    assert spec.primary == "ite8291r3_perkey"
    assert spec.auxiliary == ("ite8233_none_chassis_lightbar_clevo",)
