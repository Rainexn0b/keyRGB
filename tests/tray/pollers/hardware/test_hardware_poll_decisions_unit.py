"""Pure decision unit tests for hardware brightness polling (no tray fake)."""

from __future__ import annotations

from src.tray.pollers.hardware._decisions import (
    classify_brightness_change_persist,
    classify_off_state_change_persist,
    hardware_poll_interval_s,
    normalize_brightness_to_config_scale,
    power_source_recovery_window_active,
    should_attempt_power_source_blank_recovery,
    should_attempt_stable_zero_brightness_recovery,
)


def test_normalize_brightness_clamps_to_0_50() -> None:
    assert normalize_brightness_to_config_scale(-3) == 0
    assert normalize_brightness_to_config_scale(12) == 12
    assert normalize_brightness_to_config_scale(99) == 50
    assert normalize_brightness_to_config_scale("bad") == 0


def test_power_source_recovery_window_and_interval() -> None:
    assert power_source_recovery_window_active(
        now=10.0, last_power_source_transition_at=8.0, window_s=6.0
    )
    assert not power_source_recovery_window_active(
        now=20.0, last_power_source_transition_at=8.0, window_s=6.0
    )
    assert hardware_poll_interval_s(
        now=10.0, last_power_source_transition_at=8.0
    ) == 0.25
    assert hardware_poll_interval_s(
        now=20.0, last_power_source_transition_at=8.0
    ) == 2.0


def test_blank_recovery_eligibility_gates() -> None:
    assert should_attempt_power_source_blank_recovery(
        now=10.0,
        last_power_source_transition_at=9.0,
        last_recovery_at=0.0,
        any_forced_off=False,
        configured_brightness_intent=25,
    )
    assert not should_attempt_power_source_blank_recovery(
        now=10.0,
        last_power_source_transition_at=9.0,
        last_recovery_at=0.0,
        any_forced_off=True,
        configured_brightness_intent=25,
    )
    assert not should_attempt_power_source_blank_recovery(
        now=10.0,
        last_power_source_transition_at=9.0,
        last_recovery_at=9.8,
        any_forced_off=False,
        configured_brightness_intent=25,
        cooldown_s=0.75,
    )


def test_stable_zero_recovery_eligibility_gates() -> None:
    assert should_attempt_stable_zero_brightness_recovery(
        current_brightness=0,
        dim_temp_active=False,
        any_forced_off=False,
        configured_brightness_intent=20,
        now=100.0,
        last_recovery_at=0.0,
    )
    assert not should_attempt_stable_zero_brightness_recovery(
        current_brightness=5,
        dim_temp_active=False,
        any_forced_off=False,
        configured_brightness_intent=20,
        now=100.0,
        last_recovery_at=0.0,
    )
    assert not should_attempt_stable_zero_brightness_recovery(
        current_brightness=0,
        dim_temp_active=True,
        any_forced_off=False,
        configured_brightness_intent=20,
        now=100.0,
        last_recovery_at=0.0,
    )


def test_classify_brightness_change_mark_off_and_recover() -> None:
    mark = classify_brightness_change_persist(
        current_brightness=0,
        current_off=True,
        last_brightness=20,
        dim_temp_active=False,
        dim_temp_target=None,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=False,
    )
    assert mark.kind == "mark_off_zero"
    assert mark.track_off is True
    assert mark.refresh_ui is True

    recover = classify_brightness_change_persist(
        current_brightness=0,
        current_off=True,
        last_brightness=20,
        dim_temp_active=False,
        dim_temp_target=None,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=True,
    )
    assert recover.kind == "recover_power_source_blank"
    assert recover.track_off is False


def test_classify_brightness_dim_temp_and_clear_off() -> None:
    ignore = classify_brightness_change_persist(
        current_brightness=0,
        current_off=False,
        last_brightness=20,
        dim_temp_active=True,
        dim_temp_target=5,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=False,
    )
    assert ignore.kind == "ignore_dim_temp_transient"

    clear = classify_brightness_change_persist(
        current_brightness=25,
        current_off=False,
        last_brightness=0,
        dim_temp_active=False,
        dim_temp_target=None,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=False,
    )
    assert clear.kind == "clear_off_from_nonzero"
    assert clear.track_off is False


def test_classify_off_state_change() -> None:
    mark = classify_off_state_change_persist(
        current_brightness=10,
        current_off=True,
        last_off_state=False,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=False,
        power_source_window_active=False,
    )
    assert mark.kind == "mark_off"
    assert mark.refresh_ui is True

    window = classify_off_state_change_persist(
        current_brightness=10,
        current_off=True,
        last_off_state=False,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        power_source_blank_recoverable=False,
        power_source_window_active=True,
    )
    assert window.kind == "ignore_power_source_window"
