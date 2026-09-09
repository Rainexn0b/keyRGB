from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.settings.window as settings_window
from keyrgb.core.power.system import PowerMode
from keyrgb.gui.settings.settings_state import SettingsValues


class _FakeVar:
    def __init__(self, value=None) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.set_calls.append(value)
        self.value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))


class _FakeRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []
        self.destroy_calls = 0
        self.mainloop_calls = 0

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def destroy(self) -> None:
        self.destroy_calls += 1

    def mainloop(self) -> None:
        self.mainloop_calls += 1


def test_on_toggle_preserves_best_effort_status_when_settings_apply_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="ansi")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(False)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(False)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(False)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(False)
    gui.var_ac_brightness = _FakeVar(12.9)
    gui.var_battery_brightness = _FakeVar(8.2)
    gui.var_ac_power_mode = _FakeVar("Balanced")
    gui.var_battery_power_mode = _FakeVar("Keep current power mode")
    gui.var_dim_sync_enabled = _FakeVar(True)
    gui.var_controller_sleep_respect = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("temp")
    gui.var_dim_temp_brightness = _FakeVar(4.4)
    gui.var_debounce_enter = _FakeVar(6)
    gui.var_debounce_exit = _FakeVar(10)
    gui.var_idle_fade_duration = _FakeVar(0.6)
    gui.var_scheduler_enabled = _FakeVar(False)
    gui.var_day_start = _FakeVar("08:00")
    gui.var_night_start = _FakeVar("20:00")
    gui.var_day_base = _FakeVar(40.0)
    gui.var_day_reactive = _FakeVar(50.0)
    gui.var_night_base = _FakeVar(20.0)
    gui.var_night_reactive = _FakeVar(50.0)
    gui.var_os_autostart = _FakeVar(True)
    monkeypatch.setattr(
        settings_window,
        "apply_settings_values_to_config",
        lambda *, config, values: (_ for _ in ()).throw(OSError("save failed")),
    )
    monkeypatch.setattr(settings_window, "set_os_autostart", lambda enabled: None)
    enabled_calls: list[str] = []
    gui._apply_enabled_state = lambda: enabled_calls.append("enabled")

    gui._on_toggle()

    assert enabled_calls == ["enabled"]
    assert gui.status.configure_calls[0] == {"text": "⚠ Save failed"}


def test_on_toggle_saves_values_updates_state_and_schedules_status_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="ansi")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(False)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(False)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(False)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(False)
    gui.var_ac_brightness = _FakeVar(12.9)
    gui.var_battery_brightness = _FakeVar(8.2)
    gui.var_ac_power_mode = _FakeVar("Balanced")
    gui.var_battery_power_mode = _FakeVar("Keep current power mode")
    gui.var_dim_sync_enabled = _FakeVar(True)
    gui.var_controller_sleep_respect = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("temp")
    gui.var_dim_temp_brightness = _FakeVar(4.4)
    gui.var_debounce_enter = _FakeVar(6)
    gui.var_debounce_exit = _FakeVar(10)
    gui.var_idle_fade_duration = _FakeVar(0.6)
    gui.var_scheduler_enabled = _FakeVar(False)
    gui.var_day_start = _FakeVar("08:00")
    gui.var_night_start = _FakeVar("20:00")
    gui.var_day_base = _FakeVar(40.0)
    gui.var_day_reactive = _FakeVar(50.0)
    gui.var_night_base = _FakeVar(20.0)
    gui.var_night_reactive = _FakeVar(50.0)
    gui.var_os_autostart = _FakeVar(True)
    apply_calls: list[SettingsValues] = []
    monkeypatch.setattr(
        settings_window, "apply_settings_values_to_config", lambda *, config, values: apply_calls.append(values)
    )
    monkeypatch.setattr(settings_window, "set_os_autostart", lambda enabled: None)
    enabled_calls: list[str] = []
    gui._apply_enabled_state = lambda: enabled_calls.append("enabled")

    gui._on_toggle()

    assert apply_calls and apply_calls[0].ac_lighting_brightness == 12
    assert apply_calls[0].battery_lighting_brightness == 8
    assert apply_calls[0].ac_power_mode == PowerMode.BALANCED.value
    assert apply_calls[0].battery_power_mode is None
    # UI delays are seconds; config persists idle-poll counts (1 poll = 0.5s).
    assert apply_calls[0].idle_dim_debounce_enter_polls == 12
    assert apply_calls[0].idle_dim_debounce_exit_polls == 20
    assert apply_calls[0].physical_layout == "ansi"
    assert apply_calls[0].os_autostart_enabled is True
    assert enabled_calls == ["enabled"]
    assert gui.status.configure_calls[0] == {"text": "✓ Saved"}
    assert gui.root.after_calls[0][0] == 1500
    gui.root.after_calls[0][1]()
    assert gui.status.configure_calls[-1] == {"text": ""}


def test_on_toggle_recovers_os_autostart_var_when_set_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="auto")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(True)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(True)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(False)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(True)
    gui.var_ac_brightness = _FakeVar(10.0)
    gui.var_battery_brightness = _FakeVar(9.0)
    gui.var_ac_power_mode = _FakeVar("Keep current power mode")
    gui.var_battery_power_mode = _FakeVar("Performance")
    gui.var_dim_sync_enabled = _FakeVar(False)
    gui.var_controller_sleep_respect = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("off")
    gui.var_dim_temp_brightness = _FakeVar(5.0)
    gui.var_debounce_enter = _FakeVar(6)
    gui.var_debounce_exit = _FakeVar(10)
    gui.var_idle_fade_duration = _FakeVar(0.6)
    gui.var_scheduler_enabled = _FakeVar(False)
    gui.var_day_start = _FakeVar("08:00")
    gui.var_night_start = _FakeVar("20:00")
    gui.var_day_base = _FakeVar(40.0)
    gui.var_day_reactive = _FakeVar(50.0)
    gui.var_night_base = _FakeVar(20.0)
    gui.var_night_reactive = _FakeVar(50.0)
    gui.var_os_autostart = _FakeVar(True)
    apply_calls: list[SettingsValues] = []
    monkeypatch.setattr(
        settings_window, "apply_settings_values_to_config", lambda *, config, values: apply_calls.append(values)
    )
    monkeypatch.setattr(
        settings_window,
        "set_os_autostart",
        lambda enabled: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: False)
    gui._apply_enabled_state = lambda: None

    gui._on_toggle()

    assert gui.var_os_autostart.set_calls == [False]
    assert apply_calls[0].os_autostart_enabled is False
    assert gui.status.configure_calls[0] == {"text": "⚠ Save failed"}


def test_delay_seconds_to_polls_converts_and_clamps_to_poll_range() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    assert gui._delay_seconds_to_polls(3.0) == 6
    assert gui._delay_seconds_to_polls(0.6) == 1
    assert gui._delay_seconds_to_polls(0.0) == 1
    assert gui._delay_seconds_to_polls(0.1) == 1
    assert gui._delay_seconds_to_polls(30.0) == 60
    assert gui._delay_seconds_to_polls(120.0) == 60


def test_power_mode_selection_helpers_translate_between_labels_and_values() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    assert gui._power_mode_selection_value(PowerMode.PERFORMANCE.value) == "Performance"
    assert gui._power_mode_selection_value(None) == "Keep current power mode"
    assert gui._selected_power_mode("Extreme Saver") == PowerMode.EXTREME_SAVER.value
    assert gui._selected_power_mode("Keep current power mode") is None


def test_on_close_and_run_delegate_to_root() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()

    gui._on_close()
    gui.run()

    assert gui.root.destroy_calls == 1
    assert gui.root.mainloop_calls == 1


def test_basic_toggle_preserves_advanced_values_without_opening_advanced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UX-02: a basic Automation toggle must round-trip Advanced values.

    The window is built with fakes and the Advanced tab is never opened or
    selected (no notebook interaction); the full SettingsValues transaction
    must still carry the pre-existing advanced values unchanged.
    """
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="auto")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(False)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(False)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(True)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(False)
    gui.var_ac_brightness = _FakeVar(21.0)
    gui.var_battery_brightness = _FakeVar(9.0)
    gui.var_ac_power_mode = _FakeVar("Balanced")
    gui.var_battery_power_mode = _FakeVar("Keep current power mode")
    # Basic Automation change under test.
    gui.var_dim_sync_enabled = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("off")
    gui.var_dim_temp_brightness = _FakeVar(7.0)
    # Pre-existing Advanced values; the tab is never opened.
    gui.var_controller_sleep_respect = _FakeVar(True)
    gui.var_debounce_enter = _FakeVar(2.5)
    gui.var_debounce_exit = _FakeVar(7.5)
    gui.var_idle_fade_duration = _FakeVar(1.2)
    gui.var_scheduler_enabled = _FakeVar(False)
    gui.var_day_start = _FakeVar("08:00")
    gui.var_night_start = _FakeVar("20:00")
    gui.var_day_base = _FakeVar(40.0)
    gui.var_day_reactive = _FakeVar(50.0)
    gui.var_night_base = _FakeVar(20.0)
    gui.var_night_reactive = _FakeVar(50.0)
    gui.var_os_autostart = _FakeVar(False)
    apply_calls: list[SettingsValues] = []
    monkeypatch.setattr(
        settings_window, "apply_settings_values_to_config", lambda *, config, values: apply_calls.append(values)
    )
    monkeypatch.setattr(settings_window, "set_os_autostart", lambda enabled: None)
    enabled_calls: list[str] = []
    gui._apply_enabled_state = lambda: enabled_calls.append("enabled")

    gui._on_toggle()

    assert enabled_calls == ["enabled"]
    assert gui.status.configure_calls[0] == {"text": "✓ Saved"}
    assert len(apply_calls) == 1
    saved = apply_calls[0]
    assert saved.controller_sleep_respect is True
    assert saved.idle_dim_debounce_enter_polls == 5
    assert saved.idle_dim_debounce_exit_polls == 15
    assert saved.idle_fade_duration_s == 1.2
    assert saved.experimental_backends_enabled is True
    assert saved.screen_dim_sync_enabled is False
    assert saved.screen_dim_sync_mode == "off"
