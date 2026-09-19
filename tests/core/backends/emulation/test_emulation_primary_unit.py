"""Primary emulator selection, capabilities, and in-memory device contracts."""

from __future__ import annotations

import pytest

from keyrgb.core.backends.emulation import (
    EMULATE_ENVIRONMENT_VARIABLE,
    EmulatedPrimaryBackend,
    EmulationError,
    reset_emulated_devices,
)
from keyrgb.core.backends.registry import select_backend
from keyrgb.core.secondary_device_runtime import SIMULATION_ENVIRONMENT_VARIABLE


@pytest.fixture(autouse=True)
def _clear_emulation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EMULATE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(SIMULATION_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    reset_emulated_devices()
    yield
    reset_emulated_devices()


def test_select_backend_without_emulate_does_not_return_wrapper() -> None:
    assert select_backend() is None


def test_emulated_zones_primary_reports_real_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_zones_clevo")
    backend = select_backend()
    assert isinstance(backend, EmulatedPrimaryBackend)
    assert backend.name == "ite8291_zones_clevo"
    caps = backend.capabilities()
    assert caps.zoned is True
    assert caps.per_key is False
    assert caps.color is True
    assert backend.dimensions() == (1, 4)
    probe = backend.probe()
    assert probe.available is True
    assert probe.reason == "emulated"
    assert probe.confidence == 0
    assert probe.identifiers == {"emulated": "1", "backend": "ite8291_zones_clevo"}
    assert backend.stability.value == "experimental"


def test_emulated_primary_device_paints_and_rejects_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_zones_clevo")
    backend = select_backend()
    assert backend is not None
    device = backend.get_device()
    device.set_key_colors({(0, 0): (255, 0, 0), (0, 9): (1, 2, 3)}, brightness=40)
    assert device.get_brightness() == 40
    assert device.is_off() is False
    assert device.framebuffer()[(0, 0)] == (255, 0, 0)
    assert (0, 9) not in device.framebuffer()
    with pytest.raises(NotImplementedError, match="hardware effects"):
        device.set_effect({"effect": "wave"})
    device.close()
    device.close()
    with pytest.raises(RuntimeError, match="closed"):
        device.get_brightness()


def test_keyrgb_backend_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_zones_clevo")
    monkeypatch.setenv("KEYRGB_BACKEND", "ite8291r3_perkey")
    with pytest.raises(EmulationError, match="does not match emulated PRIMARY"):
        select_backend()


def test_emulated_primary_does_not_open_hidraw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_zones_clevo")

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("hidraw open path was called during emulation")

    monkeypatch.setattr(
        "keyrgb.core.backends.shared_hidraw_probe.open_matching_ite8291_style_hidraw_transport",
        explode,
    )
    monkeypatch.setattr(
        "keyrgb.core.backends.shared_hidraw_probe.find_matching_ite8291_style_hidraw_device",
        explode,
    )
    backend = select_backend()
    assert backend is not None
    device = backend.get_device()
    device.set_color((10, 20, 30), brightness=25)
    assert device.get_brightness() == 25


def test_keyrgb_backend_alias_of_primary_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_zones_clevo")
    monkeypatch.setenv("KEYRGB_BACKEND", "ite8291-zones")
    backend = select_backend()
    assert backend is not None
    assert backend.name == "ite8291_zones_clevo"
