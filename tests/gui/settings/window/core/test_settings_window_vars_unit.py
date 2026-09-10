"""Settings window Tk variables and enabled-state delegation."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import keyrgb.gui.settings.window as settings_window
from tests.gui.settings.window._settings_window_fakes import (
    _FakePanel,
    _FakeVar,
    _values,
)


def test_init_vars_creates_all_expected_tk_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    bool_vars: list[_FakeVar] = []
    double_vars: list[_FakeVar] = []
    string_vars: list[_FakeVar] = []
    int_vars: list[_FakeVar] = []
    monkeypatch.setattr(
        settings_window,
        "tk",
        SimpleNamespace(
            BooleanVar=lambda value=False: bool_vars.append(_FakeVar(value)) or bool_vars[-1],
            DoubleVar=lambda value=0.0: double_vars.append(_FakeVar(value)) or double_vars[-1],
            StringVar=lambda value="": string_vars.append(_FakeVar(value)) or string_vars[-1],
            IntVar=lambda value=0: int_vars.append(_FakeVar(value)) or int_vars[-1],
        ),
    )

    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    values = _values()
    gui._init_vars(values)
    assert gui.var_enabled.get() is True
    assert gui.var_off_suspend.get() is False
    assert gui.var_off_lid.get() is True
    assert gui.var_restore_resume.get() is False
    assert gui.var_restore_lid.get() is True
    assert gui.var_autostart.get() is True
    assert gui.var_experimental_backends.get() is False
    assert gui.var_os_autostart.get() is False
    assert gui.var_ac_enabled.get() is True
    assert gui.var_battery_enabled.get() is False
    assert gui.var_ac_brightness.get() == 21.0
    assert gui.var_battery_brightness.get() == 9.0
    assert gui.var_ac_power_mode.get() == "Balanced"
    assert gui.var_battery_power_mode.get() == "Keep current power mode"
    assert gui.var_dim_sync_enabled.get() is True
    assert gui.var_dim_sync_mode.get() == "temp"
    assert gui.var_dim_temp_brightness.get() == 7.0
    # UI exposes delays in seconds (0.5s steps); config stores polls.
    assert gui.var_debounce_enter.get() == 3.0
    assert gui.var_debounce_exit.get() == 5.0
    assert gui.var_idle_fade_duration.get() == 0.6
    assert gui.var_scheduler_enabled.get() is False
    assert gui.var_day_start.get() == "08:00"
    assert gui.var_night_start.get() == "20:00"
    assert gui.var_day_base.get() == 40.0
    assert gui.var_day_reactive.get() == 50.0
    assert gui.var_night_base.get() == 20.0
    assert gui.var_night_reactive.get() == 50.0
    assert len(bool_vars) == 13
    assert len(double_vars) == 10
    assert len(string_vars) == 5
    assert len(int_vars) == 0


def test_init_vars_uses_canonical_night_start_fallback_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    string_vars: list[_FakeVar] = []
    bool_vars: list[_FakeVar] = []
    double_vars: list[_FakeVar] = []
    int_vars: list[_FakeVar] = []
    monkeypatch.setattr(
        settings_window.tk, "StringVar", lambda value=None: string_vars.append(_FakeVar(value)) or string_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "BooleanVar", lambda value=None: bool_vars.append(_FakeVar(value)) or bool_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "DoubleVar", lambda value=None: double_vars.append(_FakeVar(value)) or double_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "IntVar", lambda value=None: int_vars.append(_FakeVar(value)) or int_vars[-1]
    )

    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    values = replace(_values(), night_start_time="")
    gui._init_vars(values)
    assert gui.var_night_start.get() == "20:00"


def test_apply_enabled_state_delegates_to_panels() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.var_enabled = _FakeVar(False)
    gui.management_panel = _FakePanel()
    gui.dim_sync_panel = _FakePanel()
    gui.idle_transition_advanced_panel = _FakePanel()
    gui.power_source_panel = _FakePanel()
    gui.time_scheduler_panel = _FakePanel()
    gui._apply_enabled_state()
    assert gui.management_panel.apply_calls == [{}]
    assert gui.dim_sync_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.idle_transition_advanced_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.power_source_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.time_scheduler_panel.apply_calls == [{}]
