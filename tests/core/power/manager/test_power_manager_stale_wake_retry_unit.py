"""Wake cancellation must defer, not permanently strand, a power-owned deck."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keyrgb.core.power.management import manager as manager_module
from keyrgb.core.power.management.manager import PowerManager
from keyrgb.core.power.policies.power_source_loop_policy import ActivatePerkeyProfile, PowerSourceLoopPolicy
from keyrgb.tray.controllers import lighting_controller
from keyrgb.tray.controllers.runtime_coordination import (
    active_transition_revision,
    capture_transition_revision,
    run_tray_transition,
)
from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
from keyrgb.tray.deck_pipeline import derive_deck_state, hardware_apply_deferred
from keyrgb.tray.deck_state import DeckState
from keyrgb.tray.idle_power_state import TrayIdlePowerState


class _Tray:
    def __init__(self) -> None:
        self.runtime_coordinator = TrayRuntimeCoordinator()
        self.tray_idle_power_state = TrayIdlePowerState()
        self.is_off = False
        self.config = SimpleNamespace(
            brightness=40, effect="reactive_ripple", controller_sleep_respect=True, reload=lambda: None
        )
        self.engine = MagicMock()
        self._log_event = MagicMock()
        self._refresh_ui = MagicMock()
        self._update_icon = MagicMock()
        self._update_menu = MagicMock()

    def run_runtime_transition(self, action):
        return run_tray_transition(self, action)

    def capture_runtime_transition_revision(self):
        return capture_transition_revision(self)

    def active_runtime_transition_revision(self):
        return active_transition_revision(self)

    def turn_off(self):
        lighting_controller.power_turn_off(self)

    def restore(self):
        lighting_controller.power_restore(self)


@pytest.fixture
def wake_runtime(monkeypatch):
    tray = _Tray()
    pm = PowerManager(tray, config=tray.config)
    pm._is_enabled = MagicMock(return_value=True)
    pm._flag = MagicMock(return_value=True)
    pm._classify_battery_saver_iteration = MagicMock(
        return_value=SimpleNamespace(should_sleep=False, actions=(ActivatePerkeyProfile("Red"),))
    )
    pm._activate_power_source_perkey_profile = MagicMock()
    start = MagicMock(return_value=True)
    monkeypatch.setattr(lighting_controller, "start_current_effect", start)
    monkeypatch.setattr(manager_module, "read_lid_state", lambda: "open")
    monkeypatch.setattr(manager_module.time, "sleep", lambda _seconds: None)
    try:
        yield tray, pm, start
    finally:
        assert tray.runtime_coordinator.stop_and_drain(timeout_s=1.0)


def _cancel_wake_with_queued_action(pm, tray, wake, action):
    """Queue a newer revision while the real wake route is deciding its plan."""
    deciding = threading.Event()
    release = threading.Event()

    def blocked_intent():
        deciding.set()
        assert release.wait(timeout=2.0)
        return False

    pm._get_keyboard_intent_state = MagicMock(side_effect=blocked_intent)
    before = tray.runtime_coordinator.capture_revision()
    wake_thread = threading.Thread(target=wake)
    queued_thread = threading.Thread(target=action)
    try:
        wake_thread.start()
        assert deciding.wait(timeout=1.0)
        queued_thread.start()
        deadline = time.monotonic() + 1.0
        while tray.runtime_coordinator.capture_revision() < before + 2 and time.monotonic() < deadline:
            threading.Event().wait(0.001)
        assert tray.runtime_coordinator.capture_revision() == before + 2
        release.set()
        wake_thread.join(timeout=1.0)
        queued_thread.join(timeout=1.0)
        assert not wake_thread.is_alive()
        assert not queued_thread.is_alive()
    finally:
        release.set()
        pm._get_keyboard_intent_state = MagicMock(return_value=False)


@pytest.mark.parametrize("wake_name", ["_on_resume", "_on_lid_open"])
def test_queued_source_poll_retries_stale_wake_and_unblocks_ac_profile(wake_runtime, wake_name):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    assert derive_deck_state(tray) is DeckState.POWER_OFF
    policy = PowerSourceLoopPolicy()

    _cancel_wake_with_queued_action(
        pm,
        tray,
        getattr(pm, wake_name),
        lambda: pm._run_battery_saver_iteration(policy, poll_interval_s=0.0),
    )

    start.assert_called_once()
    assert tray.is_off is False
    assert tray.tray_idle_power_state.power_forced_off is False
    assert tray._power_forced_off is False
    assert pm._event_policy.restore_pending is False
    assert derive_deck_state(tray) is DeckState.LIT
    assert hardware_apply_deferred(tray) is False
    pm._activate_power_source_perkey_profile.assert_called_once_with("Red")
    pm._run_battery_saver_iteration(policy, poll_interval_s=0.0)
    start.assert_called_once()  # The retained wake is consumed exactly once.


def test_poll_does_not_restore_before_any_wake_event(wake_runtime):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    start.assert_not_called()
    pm._classify_battery_saver_iteration.assert_not_called()
    assert tray.is_off is True


def test_pending_wake_retry_does_not_override_newer_manual_off(wake_runtime):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    _cancel_wake_with_queued_action(
        pm,
        tray,
        pm._on_resume,
        lambda: tray.run_runtime_transition(lambda: lighting_controller.turn_off(tray)),
    )
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    start.assert_not_called()
    assert derive_deck_state(tray) is DeckState.USER_OFF
    assert tray.is_off is True


def test_pending_wake_retry_does_not_override_newer_suspend(wake_runtime):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    _cancel_wake_with_queued_action(pm, tray, pm._on_resume, pm._on_suspend)
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    start.assert_not_called()
    assert derive_deck_state(tray) is DeckState.POWER_OFF


@pytest.mark.parametrize(
    "wake_name, flag_name",
    [
        ("_on_resume", "power_restore_on_resume"),
        ("_on_lid_open", "power_restore_on_lid_open"),
    ],
)
def test_pending_wake_retry_rechecks_original_action_flag(wake_runtime, wake_name, flag_name):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    _cancel_wake_with_queued_action(pm, tray, getattr(pm, wake_name), lambda: tray.run_runtime_transition(lambda: None))
    pm._flag = MagicMock(side_effect=lambda name, _default=True: name != flag_name)
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    start.assert_not_called()
    assert tray.is_off is True


@pytest.mark.parametrize("off_on_lid_close", [True, False])
def test_pending_wake_retry_respects_closed_lid_policy(wake_runtime, monkeypatch, off_on_lid_close):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    _cancel_wake_with_queued_action(pm, tray, pm._on_resume, lambda: tray.run_runtime_transition(lambda: None))
    pm._lid_closed = True
    pm._flag = MagicMock(
        side_effect=lambda name, _default=True: off_on_lid_close if name == "power_off_on_lid_close" else True
    )
    monkeypatch.setattr(manager_module, "read_lid_state", lambda: "closed")
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    assert start.call_count == (0 if off_on_lid_close else 1)
    assert tray.is_off is off_on_lid_close


def test_manual_off_on_after_lost_resume_unblocks_power_source_polling(wake_runtime):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    tray.run_runtime_transition(lambda: lighting_controller.turn_off(tray))
    tray.run_runtime_transition(lambda: lighting_controller.turn_on(tray))

    start.assert_called_once()
    assert tray.is_off is False
    assert tray.tray_idle_power_state.power_forced_off is False
    assert tray._power_forced_off is False
    assert derive_deck_state(tray) is DeckState.LIT
    assert hardware_apply_deferred(tray) is False
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    pm._activate_power_source_perkey_profile.assert_called_once_with("Red")


def test_pending_wake_retry_rechecks_global_enablement(wake_runtime):
    tray, pm, start = wake_runtime
    pm._on_suspend()
    _cancel_wake_with_queued_action(pm, tray, pm._on_resume, lambda: tray.run_runtime_transition(lambda: None))
    pm._is_enabled = MagicMock(return_value=False)
    pm._run_battery_saver_iteration(PowerSourceLoopPolicy(), poll_interval_s=0.0)
    start.assert_not_called()
    assert pm._event_policy.restore_pending is False
    assert tray.is_off is True


def test_battery_to_ac_during_sleep_applies_red_profile_after_stale_wake(wake_runtime, monkeypatch):
    """Exercise actual source stabilization, classification, and policy deduplication."""
    tray, pm, start = wake_runtime
    tray.config.ac_perkey_profile_name = "Red"
    tray.config.battery_perkey_profile_name = "Blue"
    tray.config.ac_lighting_brightness = 40
    tray.config.battery_lighting_brightness = 10
    source = {"on_ac": False, "profile": "Blue"}
    monkeypatch.setattr(manager_module, "read_on_ac_power", lambda: source["on_ac"])
    monkeypatch.setattr(manager_module, "get_active_perkey_profile", lambda: source["profile"])
    monkeypatch.setattr(manager_module, "get_system_power_status", lambda: SimpleNamespace(supported=False))
    # Use the real classifier rather than the fixture's predetermined Red action.
    del pm._classify_battery_saver_iteration
    pm._apply_brightness_policy = MagicMock(side_effect=lambda value: setattr(tray.config, "brightness", value))
    pm._activate_power_source_perkey_profile = MagicMock(side_effect=lambda name: source.update(profile=name))
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)
    pm._run_battery_saver_iteration(policy, poll_interval_s=0.0)
    assert tray.config.brightness == 10
    assert pm._stable_on_ac is False

    pm._on_suspend()
    source["on_ac"] = True
    _cancel_wake_with_queued_action(
        pm, tray, pm._on_resume, lambda: pm._run_battery_saver_iteration(policy, poll_interval_s=0.0)
    )
    pm._run_battery_saver_iteration(policy, poll_interval_s=0.0)  # Second AC observation stabilizes the source.
    assert pm._stable_on_ac is True
    assert source["profile"] == "Red"
    assert tray.config.brightness == 40
    assert tray.tray_idle_power_state.power_forced_off is False
    pm._activate_power_source_perkey_profile.assert_called_once_with("Red")
    start.assert_called_once()
