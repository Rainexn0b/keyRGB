"""Diagnostics wording and tray status labels for emulated backends."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.core.backends.emulation import EMULATE_ENVIRONMENT_VARIABLE
from keyrgb.core.diagnostics.support import _report_text as report_text
from keyrgb.core.secondary_device_runtime import (
    SIMULATION_ENVIRONMENT_VARIABLE,
    EffectiveSecondaryRoute,
    iter_effective_secondary_routes,
)
from keyrgb.tray.ui._menu_status_devices import _effective_device_context_entry, keyboard_status_text


@pytest.fixture(autouse=True)
def _clear_emulation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EMULATE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(SIMULATION_ENVIRONMENT_VARIABLE, raising=False)


def test_emulation_warning_text_is_explicit() -> None:
    assert report_text.emulation_warning_text(None) == ""
    warning = report_text.emulation_warning_text(
        {
            "backends": {
                "emulation": {"active": True, "raw": "preset:beast-x30"},
            }
        }
    )
    assert "EMULATION ACTIVE" in warning
    assert "preset:beast-x30" in warning
    assert "not hardware detection" in warning
    env = report_text.environment_text(
        {
            "system": {"os_release": {"PRETTY_NAME": "Fedora"}, "kernel_release": "6.x"},
            "env": {},
            "app": {"version": "1.0"},
            "backends": {"emulation": {"active": True, "raw": "preset:beast-x30"}},
        }
    )
    assert "EMULATION ACTIVE" in env


def test_keyboard_status_appends_emulated() -> None:
    tray = SimpleNamespace(
        backend=SimpleNamespace(name="ite8291_zones_clevo", stability="experimental"),
        backend_probe=SimpleNamespace(identifiers={"emulated": "1", "backend": "ite8291_zones_clevo"}),
        engine=SimpleNamespace(device_available=True),
    )
    text = keyboard_status_text(
        tray,
        menu_status_tray=lambda value: value,
        probe_device_available=lambda _tray: True,
        probe_identifiers=lambda value: dict(value.backend_probe.identifiers),
    )
    assert "ite8291_zones_clevo" in text
    assert "(emulated)" in text
    assert "experimental" in text


def test_auxiliary_status_uses_emulated_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMULATE_ENVIRONMENT_VARIABLE, "ite8291_none_chassis_lightbar_tongfang")
    effective = iter_effective_secondary_routes()[0]
    assert isinstance(effective, EffectiveSecondaryRoute)
    entry = _effective_device_context_entry(effective, primary_identifiers={})
    assert entry["text"].endswith("(emulated)")
    assert entry["simulated"] is True
    assert entry["source"] == "emulation"
