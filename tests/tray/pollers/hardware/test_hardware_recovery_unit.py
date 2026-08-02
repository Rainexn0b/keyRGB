"""Direct unit tests for the hardware-poll recovery group.

These tests cover the four recovery functions directly (previously only
exercised indirectly through ``_apply_polled_hardware_state``):

- ``_power_source_blank_recovery_eligible``
- ``_execute_blank_recovery``
- ``_recover_recent_power_source_blank_best_effort``
- ``_recover_stable_zero_brightness_best_effort``

Imports go through ``src.tray.pollers.hardware_polling`` so they stay valid
after the functions are extracted to a sibling module.
"""

from __future__ import annotations

import pytest

from src.tray.idle_power_state import (
    ensure_tray_idle_power_state,
    read_idle_power_state_float_field,
)
from src.tray.pollers.hardware._recovery import (
    _execute_blank_recovery,
    _power_source_blank_recovery_eligible,
    _recover_recent_power_source_blank_best_effort,
    _recover_stable_zero_brightness_best_effort,
    reset_stable_zero_recovery_attempt_count,
)
from tests.tray.fakes import make_owner_backed_simple_tray


def _make_recovery_tray(**extra) -> object:
    """Build an owner-backed tray with recovery-relevant legacy attrs preset.

    The convergence reader in ``idle_power_state`` prefers legacy
    underscore-prefixed attrs on the tray namespace over the typed owner
    field, so we set state via ``tray._<attr> = ...`` for fields the
    ``make_owner_backed_simple_tray`` builder does not recognise.
    """

    config = extra.pop("config_brightness", 25)
    tray = make_owner_backed_simple_tray(
        last_brightness=extra.pop("last_brightness", 25),
        config=type("C", (), {"brightness": config})(),
        **extra,
    )
    return tray


# ---------------------------------------------------------------------------
# _power_source_blank_recovery_eligible
# ---------------------------------------------------------------------------


def test_power_source_blank_recovery_eligible_when_conditions_met() -> None:
    """All conditions satisfied: recent transition, no forced off, intent > 0, cooldown elapsed."""

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is True


def test_power_source_blank_recovery_not_eligible_outside_window() -> None:
    """Transition was too long ago — outside the recovery window."""

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0

    # window_s is 6.0 by default; 110 - 100 = 10 > 6
    assert _power_source_blank_recovery_eligible(tray, now=110.0) is False


def test_power_source_blank_recovery_not_eligible_when_forced_off() -> None:
    tray = _make_recovery_tray(power_forced_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_not_eligible_when_brightness_intent_zero() -> None:
    tray = _make_recovery_tray(config_brightness=0, last_brightness=0)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0

    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_not_eligible_within_cooldown() -> None:
    """Recovery was attempted very recently — must wait for cooldown."""

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 100.5

    # cooldown_s is 0.75 by default; 101.0 - 100.5 = 0.5 < 0.75
    assert _power_source_blank_recovery_eligible(tray, now=101.0) is False


def test_power_source_blank_recovery_uses_monotonic_when_now_is_none(monkeypatch) -> None:
    """When now=None, the function falls back to time.monotonic()."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 101.0)

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0

    assert _power_source_blank_recovery_eligible(tray) is True


def test_power_source_blank_recovery_coerces_bad_last_recovery_at_to_zero() -> None:
    """A non-float last_recovery_at should not crash; defaults to 0.0."""

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = "not-a-float"  # type: ignore[assignment]

    # Should not raise; treat corrupt value as 0.0 (eligible since cooldown 101 - 0 > 0.75).
    assert _power_source_blank_recovery_eligible(tray, now=101.0) is True


# ---------------------------------------------------------------------------
# _execute_blank_recovery
# ---------------------------------------------------------------------------


def test_execute_blank_recovery_success_apply_transition_handled() -> None:
    """apply_transition returns truthy → recovery succeeds, full side-effect chain runs."""

    refresh_calls: list[dict] = []
    log_events: list[dict] = []
    apply_calls: list[bool] = []

    def apply_transition():
        apply_calls.append(True)
        return True

    def start_current_effect():
        raise AssertionError("should not be called when apply_transition handles it")

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = apply_transition
    tray._start_current_effect = start_current_effect
    tray._refresh_ui = lambda **kw: refresh_calls.append(kw)
    tray._log_event = lambda *_a, **kw: log_events.append({"args": _a, "fields": kw})

    result = _execute_blank_recovery(
        tray,
        current_brightness=30,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert result is True
    assert apply_calls == [True]
    # is_off was cleared
    assert tray.is_off is False
    # timestamp was written via typed owner (and converged to legacy attr)
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
        == 101.0
    )
    # log event recorded with brightness
    assert len(log_events) == 1
    assert log_events[0]["args"][1] == "power_source_blank_recover"
    assert log_events[0]["fields"]["brightness"] == 30
    # refresh called without icon animation
    assert refresh_calls == [{"animate_icon": False}]


def test_execute_blank_recovery_falls_back_to_start_current_effect() -> None:
    """When apply_transition returns falsy, start_current_effect is the fallback."""

    apply_calls: list[bool] = []
    start_calls: list[bool] = []

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: (apply_calls.append(True), False)[1]
    tray._start_current_effect = lambda: (start_calls.append(True), True)[1]
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert result is True
    assert apply_calls == [True]
    assert start_calls == [True]
    assert tray.is_off is False


def test_execute_blank_recovery_returns_false_when_no_callback_handles() -> None:
    """apply_transition falsy AND start_current_effect not callable → not handled."""

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: False
    # _start_current_effect intentionally absent
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert result is False
    # is_off was NOT cleared because recovery did not succeed
    assert tray.is_off is True


def test_execute_blank_recovery_does_not_treat_void_restart_as_success() -> None:
    tray = _make_recovery_tray(is_off=True)
    tray._apply_power_source_perkey_profile_transition = lambda: False
    tray._start_current_effect = lambda: None
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert result is False
    assert tray.is_off is True


def test_execute_blank_recovery_swallows_recoverable_exception_and_returns_false() -> None:
    """An OSError during apply_transition is logged best-effort and recovery aborts."""

    log_msgs: list[str] = []

    def boom():
        raise OSError("device busy")

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = boom
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None
    # Logger-style: first arg is a %-format string, remaining args are the substition args.
    tray._log_exception = lambda msg, *args, **_kw: log_msgs.append(str(msg))

    result = _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert result is False
    assert tray.is_off is True  # not cleared
    # The best-effort logger sees the Hardware polling error format string.
    assert any("Hardware polling error" in m for m in log_msgs)


def test_execute_blank_recovery_propagates_non_recoverable_exception() -> None:
    """A programming bug not in the recoverable set (AssertionError) must propagate."""

    def boom():
        raise AssertionError("programming bug")

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = boom
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    with pytest.raises(AssertionError, match="programming bug"):
        _execute_blank_recovery(
            tray,
            current_brightness=25,
            now=101.0,
            recovery_stamp_attr="_last_power_source_blank_recovery_at",
            recovery_stamp_state="last_power_source_blank_recovery_at",
            log_action="power_source_blank_recover",
        )


def test_execute_blank_recovery_clears_hidden_hints_in_finally_on_success() -> None:
    """The hidden hints must be cleared even on success (finally block)."""

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    # Hidden hints must be cleared (set to None on the owner).
    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None


def test_execute_blank_recovery_clears_hidden_hints_in_finally_on_failure() -> None:
    """The hidden hints must be cleared even when recovery raised a recoverable error."""

    def boom():
        raise OSError("transient")

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = boom
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None
    tray._log_exception = lambda *_a, **_kw: None

    _execute_blank_recovery(
        tray,
        current_brightness=25,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None


def test_execute_blank_recovery_sets_hidden_hints_during_apply_call() -> None:
    """The brightness hint is observable while apply_transition runs."""

    observed: dict = {}

    def spy_apply_transition():
        observed["brightness_hint"] = tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint
        observed["device_off_hint"] = tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint
        return True

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = spy_apply_transition
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    _execute_blank_recovery(
        tray,
        current_brightness=42,
        now=101.0,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )

    assert observed["brightness_hint"] == 42
    assert observed["device_off_hint"] is False


# ---------------------------------------------------------------------------
# _recover_recent_power_source_blank_best_effort
# ---------------------------------------------------------------------------


def test_recover_recent_power_source_blank_returns_false_when_not_eligible(monkeypatch) -> None:
    """When the recovery window is not active, do not attempt recovery."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 200.0)

    apply_calls: list[bool] = []

    tray = _make_recovery_tray()
    # transition was at 100.0; window=6.0; at now=200 we are well outside
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: apply_calls.append(True)
    tray._start_current_effect = lambda: None

    result = _recover_recent_power_source_blank_best_effort(tray, current_brightness=25)

    assert result is False
    assert apply_calls == []  # apply was never called


def test_recover_recent_power_source_blank_writes_power_source_stamp(monkeypatch) -> None:
    """On success, the power_source_blank recovery timestamp is written."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 101.0)

    tray = _make_recovery_tray(is_off=True)
    tray._last_power_source_transition_at = 100.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _recover_recent_power_source_blank_best_effort(tray, current_brightness=25)

    assert result is True
    # The power_source_blank stamp was updated, NOT the hardware_blank stamp.
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
        == 101.0
    )
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_hardware_blank_recovery_at",
            state_name="last_hardware_blank_recovery_at",
            default=0.0,
        )
        == 0.0
    )


# ---------------------------------------------------------------------------
# _recover_stable_zero_brightness_best_effort
# ---------------------------------------------------------------------------


def test_recover_stable_zero_returns_false_when_brightness_nonzero(monkeypatch) -> None:
    """Stable-zero recovery only fires when current_brightness is exactly 0."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=5)

    assert result is False


def test_recover_stable_zero_returns_false_when_dim_temp_active(monkeypatch) -> None:
    """Dim-temp state suppresses stable-zero recovery (treat as transient)."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray(dim_temp_active=True)
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is False


def test_recover_stable_zero_returns_false_when_any_forced_off(monkeypatch) -> None:
    """Forced-off state suppresses stable-zero recovery (intentional off)."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray(user_forced_off=True)
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is False


def test_recover_stable_zero_writes_hardware_blank_stamp(monkeypatch) -> None:
    """On success, the hardware_blank recovery timestamp is written (not the power_source one)."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray(is_off=False)
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is True
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_hardware_blank_recovery_at",
            state_name="last_hardware_blank_recovery_at",
            default=0.0,
        )
        == 100.0
    )
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
        == 0.0
    )


def test_recover_stable_zero_respects_cooldown(monkeypatch) -> None:
    """A recovery within the cooldown window is rejected."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    # last_hardware_blank_recovery_at very recent → cooldown blocks new attempt
    tray._last_hardware_blank_recovery_at = 99.5
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True

    # cooldown_s is 5.0 by default; 100.0 - 99.5 = 0.5 < 5.0
    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is False


# ---------------------------------------------------------------------------
# Circuit breaker: consecutive-attempt tracking
# ---------------------------------------------------------------------------


def test_recover_stable_zero_increments_attempt_count(monkeypatch) -> None:
    """A successful recovery increments the consecutive-attempt counter."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

    tray = _make_recovery_tray(is_off=False)
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    owner = ensure_tray_idle_power_state(tray)
    assert owner.stable_zero_recovery_attempt_count == 0

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is True
    assert owner.stable_zero_recovery_attempt_count == 1


def test_recover_stable_zero_circuit_breaker_enters_backoff(monkeypatch) -> None:
    """After max consecutive attempts, the long backoff window blocks recovery."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 110.0)

    tray = _make_recovery_tray(is_off=False)
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    # last recovery was 6 s ago: outside the 5 s cooldown but inside the 60 s
    # backoff that applies once the circuit breaker has tripped.
    tray._last_hardware_blank_recovery_at = 104.0
    tray._apply_power_source_perkey_profile_transition = lambda: True
    tray._start_current_effect = lambda: True

    owner = ensure_tray_idle_power_state(tray)
    # Already at the circuit-breaker threshold
    owner.stable_zero_recovery_attempt_count = 2

    result = _recover_stable_zero_brightness_best_effort(tray, current_brightness=0)

    assert result is False


def test_reset_stable_zero_recovery_attempt_count(monkeypatch) -> None:
    """The reset helper zeros the counter (used when brightness recovers)."""

    tray = _make_recovery_tray()
    owner = ensure_tray_idle_power_state(tray)
    owner.stable_zero_recovery_attempt_count = 5

    reset_stable_zero_recovery_attempt_count(tray)

    assert owner.stable_zero_recovery_attempt_count == 0


# ---------------------------------------------------------------------------
# Stamp-first ordering (cooldown persistence)
# ---------------------------------------------------------------------------


def test_execute_blank_recovery_writes_stamp_even_when_callback_raises(monkeypatch) -> None:
    """The cooldown stamp is written BEFORE callbacks so it persists on failure.

    This is the core fix for the cooldown bypass: if ``apply_transition`` or
    ``start_current_effect`` triggers a state-resetting side effect, the stamp
    must already be in place to block the next poll cycle.
    """

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 200.0)

    tray = _make_recovery_tray()
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0

    def _raising_apply():
        raise RuntimeError("boom")

    tray._apply_power_source_perkey_profile_transition = _raising_apply
    tray._start_current_effect = lambda: True
    tray._log_exception = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=0,
        now=200.0,
        recovery_stamp_attr="_last_hardware_blank_recovery_at",
        recovery_stamp_state="last_hardware_blank_recovery_at",
        log_action="stable_zero_brightness_recover",
    )

    # Recovery failed because the callback raised…
    assert result is False
    # …but the stamp was still written, so the cooldown will block retries.
    assert (
        read_idle_power_state_float_field(
            tray,
            attr_name="_last_hardware_blank_recovery_at",
            state_name="last_hardware_blank_recovery_at",
            default=0.0,
        )
        == 200.0
    )


# ---------------------------------------------------------------------------
# Reactive restore damp seeding (defense in depth)
# ---------------------------------------------------------------------------


def test_execute_blank_recovery_seeds_reactive_restore_damp(monkeypatch) -> None:
    """For reactive effects, restore damp is seeded before start_current_effect.

    Without this, the engine.stop() inside start_current_effect() would wipe
    _reactive_state and the first post-restart keystroke would flash at full
    pulse intensity.
    """

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 300.0)

    seeded: list[float] = []

    def _fake_seed(engine, *, fade_in_duration_s):
        seeded.append(float(fade_in_duration_s))

    # Patch the late import target so the damp-seeding helper picks it up.
    monkeypatch.setattr(
        "src.core.effects.reactive._reactive_restore_seed.seed_reactive_restore_windows",
        _fake_seed,
    )

    from types import SimpleNamespace

    engine = SimpleNamespace()
    config = SimpleNamespace(brightness=20, effect="reactive_ripple")
    tray = make_owner_backed_simple_tray(
        config=config,
        engine=engine,
    )
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0

    start_calls: list[bool] = []
    tray._apply_power_source_perkey_profile_transition = lambda: False  # not handled
    tray._start_current_effect = lambda: (start_calls.append(True), True)[1]
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=0,
        now=300.0,
        recovery_stamp_attr="_last_hardware_blank_recovery_at",
        recovery_stamp_state="last_hardware_blank_recovery_at",
        log_action="stable_zero_brightness_recover",
    )

    assert result is True
    assert start_calls == [True]
    # Damp was seeded right before the restart.
    assert seeded == [0.0]


def test_execute_blank_recovery_skips_damp_for_non_reactive_effects(monkeypatch) -> None:
    """Non-reactive effects do not trigger damp seeding."""

    monkeypatch.setattr("src.tray.pollers.hardware._recovery.time.monotonic", lambda: 300.0)

    seeded: list[float] = []

    def _fake_seed(engine, *, fade_in_duration_s):
        seeded.append(float(fade_in_duration_s))

    monkeypatch.setattr(
        "src.core.effects.reactive._reactive_restore_seed.seed_reactive_restore_windows",
        _fake_seed,
    )

    from types import SimpleNamespace

    engine = SimpleNamespace()
    config = SimpleNamespace(brightness=20, effect="wave")
    tray = make_owner_backed_simple_tray(
        config=config,
        engine=engine,
    )
    tray._last_power_source_transition_at = 0.0
    tray._last_power_source_blank_recovery_at = 0.0
    tray._last_hardware_blank_recovery_at = 0.0

    tray._apply_power_source_perkey_profile_transition = lambda: False
    tray._start_current_effect = lambda: True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _execute_blank_recovery(
        tray,
        current_brightness=0,
        now=300.0,
        recovery_stamp_attr="_last_hardware_blank_recovery_at",
        recovery_stamp_state="last_hardware_blank_recovery_at",
        log_action="stable_zero_brightness_recover",
    )

    assert result is True
    assert seeded == []
