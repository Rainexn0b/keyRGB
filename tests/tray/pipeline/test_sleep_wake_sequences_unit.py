"""Exercise real power policy/coordinator/deck transactions with fake hardware."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from keyrgb.core.effects.engine_support.brightness import _EngineBrightness
from keyrgb.core.power.management.manager import PowerManager
from keyrgb.tray.controllers import lighting_controller
from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
from keyrgb.tray.deck_pipeline import commit_sleep_wake_intent, derive_deck_state
from keyrgb.tray.deck_state import DeckState, SleepWakeIntent, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import TrayIdlePowerState


class Tray:
    def __init__(self):
        self.runtime_coordinator = TrayRuntimeCoordinator()
        self.tray_idle_power_state = TrayIdlePowerState()
        self.config = SimpleNamespace(brightness=25, effect="none", controller_sleep_respect=False, reload=lambda: None)
        self.is_off = False
        self.engine = SimpleNamespace(turn_off=Mock(), current_color=(0, 0, 0))
        self._refresh_ui = Mock()
        self._log_event = Mock()
        self._start_current_effect = Mock(return_value=True)

    def run_runtime_transition(self, action):
        return self.runtime_coordinator.run(action)

    def capture_lighting_intent_revision(self):
        return self.runtime_coordinator.capture_intent_revision()

    def active_lighting_intent_revision(self):
        return self.runtime_coordinator.active_intent_revision()

    def turn_off(self):
        return lighting_controller.power_turn_off(self)

    def restore(self):
        return lighting_controller.power_restore(self)


@pytest.fixture
def runtime(monkeypatch):
    tray = Tray()
    start = Mock(return_value=True)
    monkeypatch.setattr(lighting_controller, "start_current_effect", start)
    monkeypatch.setattr(
        lighting_controller.software_target_controller, "software_effect_target_routes_aux_devices", lambda _: False
    )
    monkeypatch.setattr(lighting_controller.secondary_static_scene, "turn_off_secondary_profile_areas", lambda _: None)
    pm = PowerManager(tray, config=tray.config)
    pm._is_enabled = lambda: True
    pm._flag = lambda *_: True
    pm._get_keyboard_intent_state = lambda: False
    clock = [100.0]
    pm._power_event_clock = lambda: clock[0]
    try:
        yield tray, pm, start, clock
    finally:
        assert tray.runtime_coordinator.stop_and_drain(timeout_s=2)


@pytest.mark.parametrize("event", ["_on_suspend", "_on_lid_close"])
def test_queued_noop_does_not_cancel_power_off(runtime, event):
    tray, pm, _, _ = runtime
    entered, release, queued = threading.Event(), threading.Event(), threading.Event()
    original = tray.runtime_coordinator._submit

    def submit(*args, **kwargs):
        command = original(*args, **kwargs)
        if command.revision == 2:
            queued.set()
        return command

    tray.runtime_coordinator._submit = submit

    def intent():
        entered.set()
        assert release.wait(2)
        return False

    pm._get_keyboard_intent_state = intent
    event_thread = threading.Thread(target=getattr(pm, event))
    poll_thread = threading.Thread(target=lambda: tray.run_runtime_transition(lambda: None))
    try:
        event_thread.start()
        assert entered.wait(2)
        poll_thread.start()
        assert queued.wait(2)
    finally:
        release.set()
        event_thread.join(2)
        poll_thread.join(2)
    assert not event_thread.is_alive() and not poll_thread.is_alive()
    tray.engine.turn_off.assert_called_once()
    assert derive_deck_state(tray) is DeckState.POWER_OFF


def resume_and_wait(tray, pm, clock):
    pm._on_resume()
    clock[0] += 0.5
    tray.run_runtime_transition(pm._retry_pending_power_restore)


@pytest.mark.parametrize("failure", [False, OSError("device not ready")])
def test_failed_power_restore_preserves_owner_and_retries(runtime, failure):
    tray, pm, start, clock = runtime
    pm._on_suspend()
    if isinstance(failure, Exception):
        start.side_effect = failure
    else:
        start.return_value = False
    resume_and_wait(tray, pm, clock)
    assert derive_deck_state(tray) is DeckState.POWER_OFF
    assert tray.is_off
    assert pm._event_policy.restore_pending
    tray.run_runtime_transition(pm._retry_pending_power_restore)
    assert start.call_count == 1  # Failed-device retries back off.
    start.side_effect = None
    start.return_value = True
    clock[0] += 2
    tray.run_runtime_transition(pm._retry_pending_power_restore)
    assert start.call_count == 2
    assert derive_deck_state(tray) is DeckState.LIT
    assert not pm._event_policy.restore_pending
    tray.run_runtime_transition(pm._retry_pending_power_restore)
    assert start.call_count == 2


def test_resume_reasserts_without_suspend_off(runtime):
    tray, pm, start, clock = runtime
    pm._flag = lambda name, _default=True: name != "power_off_on_suspend"
    pm._on_suspend()
    tray.engine.turn_off.assert_not_called()
    resume_and_wait(tray, pm, clock)
    start.assert_called_once()
    assert not pm._event_policy.restore_pending


def test_closed_lid_blocks_initial_and_retried_resume(runtime):
    tray, pm, start, clock = runtime
    pm._on_lid_close()
    pm._on_suspend()
    resume_and_wait(tray, pm, clock)
    start.assert_not_called()
    assert pm._event_policy.restore_pending
    pm._on_lid_open()
    start.assert_called_once()
    assert not pm._event_policy.restore_pending


@pytest.mark.parametrize("failure", [False, TypeError("inside start"), OSError("device not ready")])
def test_failed_idle_restore_stays_retryable(runtime, failure):
    tray, _, _, _ = runtime
    tray.tray_idle_power_state.idle_forced_off = True
    tray.is_off = True
    if isinstance(failure, Exception):
        tray._start_current_effect.side_effect = failure
    else:
        tray._start_current_effect.return_value = failure
    intent = SleepWakeIntent(SleepWakeIntentKind.SCREEN_WAKE)
    assert not tray.run_runtime_transition(lambda: commit_sleep_wake_intent(tray, intent, now=100))
    assert derive_deck_state(tray) is DeckState.IDLE_OFF
    assert tray.is_off
    tray._start_current_effect.assert_called_once()  # No TypeError-triggered second invocation.
    tray._start_current_effect.side_effect = None
    tray._start_current_effect.return_value = True
    assert tray.run_runtime_transition(lambda: commit_sleep_wake_intent(tray, intent, now=101))
    assert derive_deck_state(tray) is DeckState.LIT


class FadeEngine(_EngineBrightness):
    """Real fade/token implementation with an observable, fake device."""

    def __init__(self):
        self.kb_lock = threading.RLock()
        self._brightness_fade_lock = threading.RLock()
        self._brightness_fade_token = 0
        self.brightness = 1
        self.kb = Mock()
        self.stop = Mock()
        self._ensure_device_available = Mock(return_value=True)
        self.entered = threading.Event()
        self.release = threading.Event()

    def _fade_brightness(self, **kwargs):
        self.entered.set()
        assert self.release.wait(2)
        return super()._fade_brightness(**(kwargs | {"duration_s": 0}))


def prepare_fade(runtime):
    tray, pm, start, clock = runtime
    engine = FadeEngine()
    tray.engine = engine
    pm._on_suspend()
    engine.brightness = 1

    def start_effect(_tray, **_kwargs):
        engine.set_brightness(tray.config.brightness, fade=True)
        return True

    start.side_effect = start_effect
    resume_and_wait(tray, pm, clock)
    assert engine.entered.wait(2)
    context = tray.tray_idle_power_state.restore_context
    assert context is not None
    return tray, pm, engine, context, clock


def test_async_restore_frees_owner_and_coalesces_duplicate_wake(runtime):
    tray, pm, engine, context, _ = prepare_fade(runtime)
    try:
        assert tray.run_runtime_transition(lambda: derive_deck_state(tray)) is DeckState.RESTORING
        pm._on_resume()  # Duplicate must not orphan the original completion.
        assert tray.tray_idle_power_state.restore_context is context
        assert pm._event_policy.restore_pending
    finally:
        engine.release.set()
    assert context.completion.result(timeout=2)
    tray.run_runtime_transition(lambda: None)
    assert derive_deck_state(tray) is DeckState.LIT
    assert not pm._event_policy.restore_pending
    assert engine.kb.set_brightness.call_args.args == (25,)


def test_manual_off_cancels_restore_without_late_brightness_write(runtime):
    tray, pm, engine, context, _ = prepare_fade(runtime)
    try:
        tray.runtime_coordinator.run(lambda: lighting_controller.turn_off(tray), supersedes_lighting=True)
        assert derive_deck_state(tray) is DeckState.USER_OFF
        engine.kb.set_brightness.reset_mock()
    finally:
        engine.release.set()
    assert context.fade.result(timeout=2) is False
    tray.run_runtime_transition(lambda: None)
    engine.kb.set_brightness.assert_not_called()
    assert derive_deck_state(tray) is DeckState.USER_OFF
    assert not pm._event_policy.restore_pending


def test_async_device_failure_rolls_back_and_retries(runtime):
    tray, pm, engine, context, clock = prepare_fade(runtime)
    engine.kb.set_brightness.side_effect = OSError("disconnected")
    engine.release.set()
    assert not context.completion.result(timeout=2)
    tray.run_runtime_transition(lambda: None)
    assert derive_deck_state(tray) is DeckState.POWER_OFF
    assert pm._event_policy.restore_pending
    engine.kb.set_brightness.side_effect = None
    clock[0] += 2
    tray.run_runtime_transition(pm._retry_pending_power_restore)
    completion = pm._pending_power_restore_future
    if completion is not None:
        assert completion.result(timeout=2)
    tray.run_runtime_transition(lambda: None)
    assert derive_deck_state(tray) is DeckState.LIT
    assert not pm._event_policy.restore_pending


def test_async_cleanup_failure_settles_restore_and_allows_retry(runtime):
    tray, pm, engine, context, clock = prepare_fade(runtime)
    engine.kb.set_brightness.side_effect = OSError("disconnected")
    engine.stop.side_effect = RuntimeError("worker join failed")
    engine.release.set()
    assert not context.completion.result(timeout=2)
    tray.run_runtime_transition(lambda: None)
    assert derive_deck_state(tray) is DeckState.POWER_OFF
    assert tray.tray_idle_power_state.restore_context is None
    assert pm._pending_power_restore_future is None
    assert pm._event_policy.restore_pending
    engine.stop.side_effect = None
    engine.kb.set_brightness.side_effect = None
    clock[0] += 2
    tray.run_runtime_transition(pm._retry_pending_power_restore)
    completion = pm._pending_power_restore_future
    if completion is not None:
        assert completion.result(timeout=2)
    tray.run_runtime_transition(lambda: None)
    assert derive_deck_state(tray) is DeckState.LIT
    assert not pm._event_policy.restore_pending


def test_brightness_edit_during_restore_applies_latest_intent_once(runtime):
    from keyrgb.tray.controllers._brightness_layer import apply_layered_brightness_update

    tray, pm, engine, context, _ = prepare_fade(runtime)
    try:
        for brightness in (30, 35):
            tray.run_runtime_transition(
                lambda value=brightness: apply_layered_brightness_update(
                    tray,
                    source="menu",
                    base_brightness=value,
                    reactive_brightness=None,
                    start_current_effect=lambda _tray: True,
                    defer_hardware_apply=True,
                )
            )
        assert tray.config.brightness == 35
        assert derive_deck_state(tray) is DeckState.RESTORING
        assert engine.brightness == 1
        assert pm._keyboard_is_power_event_forced_off()
    finally:
        engine.release.set()
    assert context.completion.result(timeout=2)
    assert engine.brightness == 35
    assert runtime[2].call_count == 2  # One original start plus one coalesced edit.


@pytest.mark.parametrize("brightness, current_off", [(0, True), (60, False)])
def test_hardware_poll_cannot_adopt_or_heal_an_inflight_restore(runtime, monkeypatch, brightness, current_off):
    from keyrgb.tray.pollers import hardware_polling as hp

    tray, _, engine, context, _ = prepare_fade(runtime)
    recover = Mock(return_value=True)
    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", recover)
    monkeypatch.setattr(hp, "_recover_recent_power_source_blank_best_effort", recover)
    try:
        tray.run_runtime_transition(
            lambda: hp._apply_polled_hardware_state(
                tray,
                raw_brightness=brightness,
                current_brightness=brightness,
                current_off=current_off,
                last_brightness=25,
                last_off_state=False,
            )
        )
        recover.assert_not_called()
        assert not tray.is_off
        assert derive_deck_state(tray) is DeckState.RESTORING
    finally:
        engine.release.set()
    assert context.completion.result(timeout=2)


def test_lid_open_cannot_release_suspend_cause(runtime):
    tray, pm, start, clock = runtime
    pm._on_lid_close()
    pm._on_suspend()
    pm._on_lid_open()
    start.assert_not_called()
    assert derive_deck_state(tray) is DeckState.POWER_OFF
    resume_and_wait(tray, pm, clock)
    start.assert_called_once()


def test_disabled_resume_does_not_consume_closed_lid_restore(runtime):
    tray, pm, start, clock = runtime
    pm._flag = lambda name, _default=True: name != "power_restore_on_resume"
    pm._on_lid_close()
    pm._on_suspend()
    pm._on_resume()
    start.assert_not_called()
    clock[0] += 0.5
    pm._on_lid_open()
    start.assert_called_once()
    assert derive_deck_state(tray) is DeckState.LIT
