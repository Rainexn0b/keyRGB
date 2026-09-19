"""Named auxiliary emulation replaces all-or-nothing secondary simulation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from keyrgb.core.backends.emulation import EMULATE_ENVIRONMENT_VARIABLE
from keyrgb.core.secondary_device_routes import SecondaryDeviceRoute
from keyrgb.core.secondary_device_runtime import (
    SIMULATION_ENVIRONMENT_VARIABLE,
    acquire_secondary_device,
    backend_for_secondary_route,
    iter_effective_secondary_routes,
    reset_simulated_secondary_devices,
    route_is_available,
)


def _route(device_type: str, *, state_key: str) -> SecondaryDeviceRoute:
    return SecondaryDeviceRoute(
        device_type=device_type,
        backend_name=f"test-{device_type}",
        display_name=device_type.title(),
        state_key=state_key,
        get_backend=lambda: None,
        get_device=lambda: object(),
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
    )


@pytest.fixture(autouse=True)
def _clear_emulation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EMULATE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(SIMULATION_ENVIRONMENT_VARIABLE, raising=False)
    reset_simulated_secondary_devices()
    yield
    reset_simulated_secondary_devices()


def test_named_emulation_exposes_only_listed_auxiliary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_none_chassis_lightbar_tongfang")
    effective = iter_effective_secondary_routes()
    assert [entry.state_key for entry in effective] == ["ite8291_tongfang_lightbar"]
    assert effective[0].simulated is True
    assert effective[0].availability_source == "emulation"
    assert "Clevo" not in effective[0].display_name


def test_legacy_flag_still_exposes_all_six_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    effective = iter_effective_secondary_routes()
    assert [entry.state_key for entry in effective] == [
        "lightbar",
        "ite8291_tongfang_lightbar",
        "mouse",
        "ite8258_chassis_logo",
        "ite8258_chassis_neon",
        "ite8258_chassis_vent",
    ]
    assert {entry.availability_source for entry in effective} == {"simulation"}


def test_legion_preset_exposes_virtual_children(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "preset:legion-gen10")
    effective = iter_effective_secondary_routes()
    assert [entry.state_key for entry in effective] == [
        "ite8258_chassis_logo",
        "ite8258_chassis_neon",
        "ite8258_chassis_vent",
    ]
    assert all(entry.availability_source == "emulation" for entry in effective)


def test_named_emulation_never_calls_real_probe_or_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_none_chassis_lightbar_tongfang")

    def explode_probe():
        raise AssertionError("real secondary backend probe was called")

    def explode_device():
        raise AssertionError("real secondary get_device was called")

    tongfang = replace(
        _route("lightbar", state_key="ite8291_tongfang_lightbar"),
        backend_name="ite8291_none_chassis_lightbar_tongfang",
        get_backend=explode_probe,
        get_device=explode_device,
    )
    clevo = replace(
        _route("lightbar", state_key="lightbar"),
        backend_name="ite8233_none_chassis_lightbar_clevo",
        get_backend=explode_probe,
        get_device=explode_device,
    )

    effective = iter_effective_secondary_routes([tongfang, clevo])
    assert [entry.state_key for entry in effective] == ["ite8291_tongfang_lightbar"]
    assert route_is_available(tongfang) is True
    device = acquire_secondary_device(tongfang)
    assert device.device_type == "lightbar"
    assert backend_for_secondary_route(tongfang).is_available() is True
