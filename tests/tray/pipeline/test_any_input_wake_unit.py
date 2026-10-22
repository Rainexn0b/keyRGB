"""Any-input wake through the real idle loop, coordinator and restore pipeline."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from keyrgb.core.effects.device import KeyboardDeviceProtocol
from keyrgb.core.effects.engine import EffectsEngine
from keyrgb.core.effects.engine_support import core
from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
from keyrgb.tray.deck_pipeline import commit_sleep_wake_intent, derive_deck_state
from keyrgb.tray.deck_state import DeckState, SleepWakeIntent, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import set_idle_power_state_field
from keyrgb.tray.pollers.idle_power import _actions, _input_wake, _runtime, polling
from keyrgb.tray.pollers.idle_power.policy import compute_idle_action
from tests.tray.fakes import make_owner_backed_simple_tray


def set_owner(tray, name, value):
    set_idle_power_state_field(tray, attr_name=f"_{name}", state_name=name, value=value)


@pytest.fixture
def wake_runtime(monkeypatch):
    clock = [110.0]
    monkeypatch.setattr(_actions.time, "monotonic", lambda: clock[0])
    keyboard = Mock(spec=KeyboardDeviceProtocol)
    keyboard.get_brightness.return_value = 0
    keyboard.is_off.return_value = False
    keyboard.keyrgb_controller_wake_settle_s = 0.0
    monkeypatch.setattr(core, "acquire_keyboard", Mock(return_value=(keyboard, True)))
    start = Mock(return_value=True)
    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(
            reload=lambda: None,
            brightness=25,
            effect="none",
            controller_sleep_respect=True,
            wake_on_any_input=True,
            power_management_enabled=True,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
        ),
        engine=EffectsEngine(),
        runtime_coordinator=TrayRuntimeCoordinator(),
        is_off=True,
        _start_current_effect=start,
        _refresh_ui=Mock(),
        _log_event=Mock(),
    )
    set_owner(tray, "controller_sleep_off", True)
    set_owner(tray, "controller_sleep_off_at", 100.0)
    evdev = SimpleNamespace(last_wake_activity_at=105.0, last_keyboard_activity_at=0.0)
    pointer = SimpleNamespace(last_activity_at=0.0, idle=False, close=Mock())
    desktop = SimpleNamespace(idle=False)
    create_wayland = Mock(side_effect=lambda timeout: pointer if timeout == 0 else desktop)
    loop = _runtime.IdlePollLoopState()

    def tick(*, screen_off=False):
        _runtime.run_idle_power_iteration(
            tray,
            loop_state=loop,
            idle_timeout_s=60,
            session_id=None,
            now_monotonic_fn=lambda: clock[0],
            ensure_idle_state_fn=lambda _: None,
            read_dimmed_state_fn=lambda _: False,
            read_screen_off_state_drm_fn=lambda: screen_off,
            debounce_dim_and_screen_off_fn=lambda **kw: (kw["dimmed_raw"], kw["screen_off_raw"], 0, 0, 0),
            read_logind_idle_seconds_fn=lambda **_: None,
            read_desktop_dim_timeout_fn=lambda _: 60,
            create_wayland_idle_tracker_fn=create_wayland,
            read_wayland_idle_fn=lambda tracker: tracker.idle,
            create_input_idle_tracker_fn=lambda: evdev,
            read_input_idle_seconds_fn=lambda _: 0.0,
            effective_screen_dim_sync_enabled_fn=lambda _tray, enabled: enabled,
            compute_idle_action_fn=compute_idle_action,
            build_idle_action_key_fn=lambda **kw: str(kw["action"]),
            should_log_idle_action_fn=lambda **_: False,
            apply_idle_action_fn=polling._apply_idle_action,
            read_on_ac_power_fn=lambda: True,
        )

    runtime = SimpleNamespace(
        tray=tray,
        keyboard=keyboard,
        start=start,
        evdev=evdev,
        pointer=pointer,
        desktop=desktop,
        create_wayland=create_wayland,
        loop=loop,
        tick=tick,
        clock=clock,
    )
    try:
        yield runtime
    finally:
        loop.input_wake.close()
        assert tray.runtime_coordinator.stop_and_drain(timeout_s=2)
        tray.engine.close()


def test_cold_controller_input_wake_uses_explicit_soft_on_once(wake_runtime):
    r = wake_runtime
    r.tick()
    r.start.assert_called_once_with(brightness_override=1, fade_in=True, fade_in_duration_s=0.6)
    assert derive_deck_state(r.tray) is DeckState.LIT
    assert r.tray.tray_idle_power_state.controller_sleep_resume_guard
    r.tick()
    assert r.start.call_count == 1
    r.keyboard.turn_off.assert_not_called()


def test_already_awake_firmware_keeps_native_brightness_handoff(wake_runtime):
    r = wake_runtime
    r.keyboard.get_brightness.return_value = 50
    r.tick()
    r.start.assert_called_once_with(brightness_override=None, controller_brightness_handoff=50)
    r.keyboard.turn_off.assert_not_called()


def test_input_settle_waits_once_without_fabricating_firmware_wake(wake_runtime):
    r = wake_runtime
    r.keyboard.keyrgb_controller_wake_settle_s = 2.5
    r.evdev.last_wake_activity_at = 109.5
    r.tick()
    r.start.assert_not_called()
    assert r.loop.input_wake.wake_not_before == 112.0
    assert r.tray.tray_idle_power_state.controller_wake_settle_until == 0.0
    r.evdev.last_wake_activity_at = 110.5
    r.clock[0] = 111.0
    r.tick()
    r.start.assert_not_called()
    assert r.loop.input_wake.wake_not_before == 112.0
    r.clock[0] = 112.0
    r.tick()
    r.start.assert_called_once()
    assert derive_deck_state(r.tray) is DeckState.LIT


def test_later_firmware_wake_keeps_its_own_settle_deadline(wake_runtime):
    r = wake_runtime
    r.keyboard.keyrgb_controller_wake_settle_s = 2.5
    r.evdev.last_wake_activity_at = 109.5  # Pointer, controller still dark.
    r.tick()
    r.start.assert_not_called()
    # A key wakes firmware just before the pointer's host-wake deadline. Time
    # spent waiting on a dark controller is not firmware-settling evidence.
    r.keyboard.get_brightness.return_value = 50
    r.evdev.last_wake_activity_at = 111.9
    r.clock[0] = 112.0
    r.tick()
    r.start.assert_not_called()
    assert r.tray.tray_idle_power_state.controller_wake_settle_until == 114.5
    r.clock[0] = 113.0
    r.tick()
    r.start.assert_not_called()
    r.clock[0] = 114.5
    r.tick()
    r.start.assert_called_once_with(brightness_override=None, controller_brightness_handoff=50)
    assert derive_deck_state(r.tray) is DeckState.LIT


@pytest.mark.parametrize("brightness", [0, 50])
def test_any_input_preserves_temporary_dim_limit(wake_runtime, brightness):
    r = wake_runtime
    set_owner(r.tray, "dim_temp_active", True)
    set_owner(r.tray, "dim_temp_target_brightness", 5)
    r.keyboard.get_brightness.return_value = brightness
    r.tick()
    assert r.start.call_args.kwargs["brightness_override"] == 5
    assert derive_deck_state(r.tray) is DeckState.DIM_TEMP
    assert r.tray.tray_idle_power_state.dim_temp_target_brightness == 5


@pytest.mark.parametrize("blocker", ["user_forced_off", "power_forced_off"])
def test_input_cannot_override_manual_or_power_off(wake_runtime, blocker):
    r = wake_runtime
    set_owner(r.tray, blocker, True)
    r.tick()
    r.start.assert_not_called()
    assert r.tray.is_off
    r.keyboard.get_brightness.assert_not_called()


def test_default_policy_keeps_modifier_and_pointer_activity_dark(wake_runtime):
    r = wake_runtime
    r.tray.config.wake_on_any_input = False
    r.tick()
    r.start.assert_not_called()
    assert all(call.args != (0,) for call in r.create_wayland.call_args_list)


@pytest.mark.parametrize("activity_at", [0.0, 95.0, 100.0])
def test_startup_and_pre_sleep_events_do_not_restore(wake_runtime, activity_at):
    r = wake_runtime
    r.evdev.last_wake_activity_at = activity_at
    r.tick()
    r.start.assert_not_called()
    assert r.loop.input_wake.tracker is r.pointer
    assert r.tray.is_off


def test_wayland_pointer_event_restores_without_evdev_input(wake_runtime):
    r = wake_runtime
    r.evdev.last_wake_activity_at = 0.0
    r.tick()  # Creates listener; active state alone does nothing.
    r.start.assert_not_called()
    r.pointer.last_activity_at = 109.0
    r.pointer.idle = True  # Movement already ended before the next poll.
    r.tick()
    r.start.assert_called_once()
    r.tick()
    r.pointer.close.assert_called_once()


def test_failed_input_restore_keeps_owner_and_can_retry(wake_runtime):
    r = wake_runtime
    r.start.return_value = False
    r.tick()
    assert derive_deck_state(r.tray) is DeckState.CONTROLLER_SLEEP_DARK
    assert r.tray.is_off
    assert r.tray.tray_idle_power_state.restore_context is None
    r.start.return_value = True
    r.tick()
    assert derive_deck_state(r.tray) is DeckState.LIT
    assert r.start.call_count == 2


def test_controller_probe_failure_does_not_guess_firmware_is_awake(wake_runtime):
    r = wake_runtime
    r.keyboard.get_brightness.side_effect = OSError("disconnected")
    r.tick()
    r.start.assert_not_called()
    assert derive_deck_state(r.tray) is DeckState.CONTROLLER_SLEEP_DARK
    r.keyboard.get_brightness.side_effect = None
    r.tick()
    r.start.assert_called_once()


@pytest.mark.parametrize("native_sleep", [False, True])
def test_screen_idle_input_wake_keeps_screen_and_debounce_gates(wake_runtime, native_sleep):
    r = wake_runtime
    set_owner(r.tray, "controller_sleep_off", native_sleep)
    set_owner(r.tray, "idle_forced_off", True)
    set_owner(r.tray, "last_idle_turn_off_at", 109.0)
    r.evdev.last_wake_activity_at = 109.5
    r.tick()
    r.start.assert_not_called()  # Existing 2.5-second off/restore suppression.
    r.clock[0] = 113.0
    r.tick(screen_off=True)
    r.start.assert_not_called()
    r.tick(screen_off=False)
    r.start.assert_called_once()
    assert derive_deck_state(r.tray) is DeckState.LIT


def test_overlapping_idle_off_requires_input_after_latest_off(wake_runtime):
    r = wake_runtime
    set_owner(r.tray, "idle_forced_off", True)
    set_owner(r.tray, "last_idle_turn_off_at", 108.0)
    r.clock[0] = 112.0
    r.tick()
    r.start.assert_not_called()  # Existing event predates the newer idle off.
    r.evdev.last_wake_activity_at = 111.0
    r.tick()
    r.start.assert_called_once()
    assert derive_deck_state(r.tray) is DeckState.LIT


def test_wayland_disconnect_retries_without_replaying_old_activity(wake_runtime):
    r = wake_runtime
    r.evdev.last_wake_activity_at = 0.0
    r.pointer.last_activity_at = 109.0
    r.pointer.idle = None  # Disconnected: old activity is no longer evidence.
    r.tick()
    r.start.assert_not_called()
    r.pointer.close.assert_called_once()
    assert r.loop.input_wake.tracker is None
    requests = r.create_wayland.call_count
    r.clock[0] = 111.0
    r.tick()
    assert r.create_wayland.call_count == requests
    reconnected = SimpleNamespace(last_activity_at=0.0, idle=False, close=Mock())
    r.create_wayland.side_effect = lambda timeout: reconnected if timeout == 0 else r.desktop
    r.clock[0] = 115.0
    r.tick()
    r.start.assert_not_called()  # Active after reconnect is not a new input.
    reconnected.last_activity_at = 116.0
    r.clock[0] = 116.0
    r.tick()
    r.start.assert_called_once()


def test_disabling_input_wake_closes_listener_and_preserves_keyboard_only_policy(wake_runtime):
    r = wake_runtime
    r.evdev.last_wake_activity_at = 0.0
    r.tick()
    r.pointer.last_activity_at = 109.0
    r.tray.config.wake_on_any_input = False
    r.tick()
    r.pointer.close.assert_called_once()
    r.start.assert_not_called()


def test_zero_configured_brightness_is_not_rewritten_by_input(wake_runtime):
    r = wake_runtime
    r.tray.config.brightness = 0
    r.tick()
    r.start.assert_not_called()
    assert r.tray.config.brightness == 0


@pytest.mark.parametrize("superseding", ["off", "firmware", "new_epoch", "disable"])
def test_late_input_evidence_cannot_supersede_newer_state(wake_runtime, superseding):
    r = wake_runtime
    evidence = _input_wake.InputWakeEvidence(DeckState.CONTROLLER_SLEEP_DARK, 100.0, 105.0)
    coordinator = r.tray.runtime_coordinator
    revision = coordinator.capture_revision()
    if superseding == "off":
        coordinator.run(lambda: set_owner(r.tray, "user_forced_off", True), supersedes_lighting=True)
    elif superseding == "firmware":
        coordinator.run(
            lambda: commit_sleep_wake_intent(
                r.tray, SleepWakeIntent(SleepWakeIntentKind.FIRMWARE_WAKE), now=110, current_brightness=50
            )
        )
    elif superseding == "new_epoch":
        set_owner(r.tray, "controller_sleep_off_at", 108.0)
    else:
        r.tray.config.wake_on_any_input = False
    starts = r.start.call_count
    _input_wake.commit_input_wake(r.tray, evidence, now=110, observation_revision=revision)
    assert r.start.call_count == starts


def test_duplicate_input_during_async_restore_does_not_start_second_fade(wake_runtime, monkeypatch):
    r = wake_runtime
    entered, release = Event(), Event()
    fade = r.tray.engine._fade_brightness
    r.tray.engine.brightness = 1

    def paused_fade(**kwargs):
        entered.set()
        assert release.wait(2)
        return fade(**kwargs)

    def start(**kwargs):
        r.tray.engine.set_brightness(25, fade=True, fade_duration_s=0)
        return True

    monkeypatch.setattr(r.tray.engine, "_fade_brightness", paused_fade)
    r.start.side_effect = start
    try:
        r.tick()
        assert entered.wait(2)
        context = r.tray.tray_idle_power_state.restore_context
        assert context is not None
        r.tick()
        assert r.start.call_count == 1
    finally:
        release.set()
    assert context.completion.result(timeout=2)
    assert derive_deck_state(r.tray) is DeckState.LIT
