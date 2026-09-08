"""Unit tests for zero-brightness recovery and controller sleep handling."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from keyrgb.tray.deck_pipeline import _commit_firmware_wake
from keyrgb.tray.idle_power_state import (
    ensure_tray_idle_power_state,
    read_idle_power_state_float_field,
)
from keyrgb.tray.pollers.hardware import _controller_sleep, _runtime_support
from keyrgb.tray.pollers.hardware._recovery import (
    _recover_recent_power_source_blank_best_effort,
    _recover_stable_zero_brightness_best_effort,
    reset_stable_zero_recovery_attempt_count,
)
from tests.tray.fakes import make_owner_backed_simple_tray


def _make_recovery_tray(**extra) -> object:
    """Build an owner-backed tray with recovery-relevant legacy attrs preset."""

    config = extra.pop("config_brightness", 25)
    tray = make_owner_backed_simple_tray(
        last_brightness=extra.pop("last_brightness", 25),
        config=type("C", (), {"brightness": config})(),
        **extra,
    )
    return tray


def test_recover_recent_power_source_blank_returns_false_when_not_eligible(monkeypatch) -> None:
    """When the recovery window is not active, do not attempt recovery."""

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 200.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 101.0)

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


def test_recover_stable_zero_returns_false_when_brightness_nonzero(monkeypatch) -> None:
    """Stable-zero recovery only fires when current_brightness is exactly 0."""

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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


def test_recover_stable_zero_increments_attempt_count(monkeypatch) -> None:
    """A successful recovery increments the consecutive-attempt counter."""

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 100.0)

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

    monkeypatch.setattr("keyrgb.tray.pollers.hardware._recovery.time.monotonic", lambda: 110.0)

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


def test_controller_sleep_helpers_classify_stop_and_clear_final_frame() -> None:
    calls: list[str] = []
    keyboard = SimpleNamespace(
        get_brightness=lambda: 8,
        turn_off=lambda: calls.append("turn_off"),
    )
    engine = SimpleNamespace(
        kb=keyboard,
        kb_lock=threading.RLock(),
        stop=lambda: calls.append("stop"),
        _device_mode_off=False,
    )
    tray = SimpleNamespace(engine=engine)

    assert _controller_sleep.classify_polled_state(tray, current_brightness=0, current_off=False) is True
    assert _controller_sleep.stop_engine_for_controller_sleep_best_effort(tray) is True
    _controller_sleep.clear_post_stop_write_best_effort(tray)

    assert calls == ["stop", "turn_off"]
    assert engine._device_mode_off is True


def test_controller_sleep_helpers_keep_native_zero_and_contain_runtime_failures() -> None:
    zero_calls: list[str] = []
    zero_tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb=SimpleNamespace(
                get_brightness=lambda: 0,
                turn_off=lambda: zero_calls.append("turn_off"),
            ),
            kb_lock=threading.RLock(),
        )
    )
    _controller_sleep.clear_post_stop_write_best_effort(zero_tray)
    assert zero_calls == []

    failed_stop_tray = SimpleNamespace(
        engine=SimpleNamespace(
            stop=lambda: (_ for _ in ()).throw(OSError("unavailable")),
            _device_mode_off=False,
        )
    )
    assert _controller_sleep.stop_engine_for_controller_sleep_best_effort(failed_stop_tray) is False

    failed_read_tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb=SimpleNamespace(get_brightness=lambda: (_ for _ in ()).throw(OSError("unavailable"))),
            kb_lock=threading.RLock(),
        )
    )
    _controller_sleep.clear_post_stop_write_best_effort(failed_read_tray)


def test_firmware_wake_restart_stamps_resume_and_accepts_void_callback() -> None:
    calls: list[str] = []
    tray = make_owner_backed_simple_tray(
        engine=SimpleNamespace(),
        _start_current_effect=lambda: calls.append("start"),
        last_resume_at=0.0,
    )

    assert _controller_sleep.restart_effect_after_firmware_wake_best_effort(tray, now=123.5) is True
    assert calls == ["start"]
    assert tray.tray_idle_power_state.last_resume_at == 123.5


def test_firmware_wake_handoff_preserves_legacy_start_callback() -> None:
    calls: list[str] = []
    tray = make_owner_backed_simple_tray(
        engine=SimpleNamespace(),
        _start_current_effect=lambda: calls.append("start"),
        last_resume_at=0.0,
    )

    assert (
        _controller_sleep.restart_effect_after_firmware_wake_best_effort(
            tray,
            now=123.5,
            controller_brightness_handoff=50,
        )
        is True
    )
    assert calls == ["start"]
    assert tray.tray_idle_power_state.last_resume_at == 123.5


def test_firmware_wake_commit_adapts_legacy_restarter_then_refreshes_lit_state() -> None:
    calls: list[tuple[float, int | None]] = []
    refreshed: list[tuple[bool, bool]] = []
    tray = _make_recovery_tray(is_off=True, controller_sleep_off=True)
    tray.engine = SimpleNamespace(kb=SimpleNamespace(keyrgb_controller_wake_settle_s=0.0))
    tray._log_event = lambda *_a, **_kw: None
    tray._refresh_ui = lambda **_kwargs: refreshed.append(
        (bool(tray.is_off), bool(tray.tray_idle_power_state.controller_sleep_off))
    )

    def legacy_restarter(_tray, *, now: float, brightness_override: int | None) -> bool:
        calls.append((float(now), brightness_override))
        return True

    result = _commit_firmware_wake(
        tray,
        now=123.5,
        current_brightness=50,
        dim_temp_target=None,
        restart_firmware_wake=legacy_restarter,
    )

    assert result is True
    assert calls == [(123.5, None)]
    assert refreshed == [(False, False)]


def test_firmware_wake_restart_uses_public_fallback(monkeypatch) -> None:
    calls: list[object] = []
    tray = make_owner_backed_simple_tray(engine=SimpleNamespace(), last_resume_at=0.0)
    monkeypatch.setattr(
        "keyrgb.tray.controllers.lighting_controller.start_current_effect",
        lambda target, **kwargs: calls.append(target) or True,
    )

    assert _controller_sleep.restart_effect_after_firmware_wake_best_effort(tray, now=50.0) is True
    assert calls == [tray]


def test_firmware_wake_restart_logs_recoverable_callback_failure(monkeypatch) -> None:
    logged: list[Exception] = []
    tray = make_owner_backed_simple_tray(
        engine=SimpleNamespace(),
        _start_current_effect=lambda: (_ for _ in ()).throw(RuntimeError("start failed")),
    )
    monkeypatch.setattr(
        _controller_sleep._recovery,
        "_log_hardware_polling_error_best_effort",
        lambda _tray, exc: logged.append(exc),
    )

    assert _controller_sleep.restart_effect_after_firmware_wake_best_effort(tray, now=75.0) is False
    assert len(logged) == 1


def test_runtime_support_reads_pulse_mix_and_contains_bad_runtime_value(monkeypatch) -> None:
    tray = SimpleNamespace(engine=object())
    monkeypatch.setattr(
        _runtime_support,
        "_reactive_active_pulse_mix_or_default",
        lambda _engine, *, default: 0.625,
    )
    assert _runtime_support.reactive_pulse_mix_or_zero(tray) == 0.625

    monkeypatch.setattr(
        _runtime_support,
        "_reactive_active_pulse_mix_or_default",
        lambda _engine, *, default: (_ for _ in ()).throw(ValueError("bad pulse")),
    )
    assert _runtime_support.reactive_pulse_mix_or_zero(tray) == 0.0


def test_runtime_support_polls_coherent_snapshot() -> None:
    observed: list[dict[str, object]] = []
    tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb=SimpleNamespace(get_brightness=lambda: 17, is_off=lambda: False),
            kb_lock=threading.RLock(),
        )
    )

    def apply_state(target, **fields):
        observed.append({"tray": target, **fields})
        return 17, False

    result = _runtime_support.poll_hardware_once(
        tray,
        last_brightness=10,
        last_off_state=True,
        apply_polled_state_fn=apply_state,
    )

    assert result == (17, False)
    assert observed == [
        {
            "tray": tray,
            "raw_brightness": 17,
            "current_brightness": 17,
            "current_off": False,
            "last_brightness": 10,
            "last_off_state": True,
        }
    ]
