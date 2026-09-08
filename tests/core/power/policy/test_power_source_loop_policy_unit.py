from __future__ import annotations

from keyrgb.core.power.policies.power_source_loop_policy import (
    ActivatePerkeyProfile,
    ActivatePowerMode,
    PowerSourceLoopPolicy,
    RestoreKeyboard,
    TurnOffKeyboard,
)
from keyrgb.core.power.system import PowerMode
from tests.core.power.policy._power_source_loop_support import make_inputs as _inputs


def test_power_source_loop_policy_debounces_power_flapping() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=3.0)

    first = policy.update(
        _inputs(
            on_ac=True,
            now=0.0,
        )
    )
    assert first.skip is False

    flapping = policy.update(
        _inputs(
            on_ac=False,
            now=1.0,
        )
    )
    assert flapping.skip is True
    assert flapping.actions == ()


def test_power_source_loop_policy_emits_enable_disable_actions() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    # First tick on AC, AC disabled -> should request turn off.
    res = policy.update(
        _inputs(
            ac_enabled=False,
        )
    )
    assert any(isinstance(a, TurnOffKeyboard) for a in res.actions)

    # Now enable AC lighting -> should request restore.
    res2 = policy.update(
        _inputs(
            now=10.0,
        )
    )
    assert any(isinstance(a, RestoreKeyboard) for a in res2.actions)


def test_power_source_loop_policy_does_not_restore_on_first_tick_when_already_on() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs())

    assert res.actions == ()


def test_power_source_loop_policy_restores_on_first_tick_when_currently_off() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(current_brightness=0, is_off=True))

    assert any(isinstance(a, RestoreKeyboard) for a in res.actions)


def test_power_source_loop_policy_activates_selected_power_mode_on_first_tick_when_needed() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(active_power_mode=PowerMode.PERFORMANCE, ac_power_mode=PowerMode.BALANCED))

    assert ActivatePowerMode(PowerMode.BALANCED) in res.actions


def test_power_source_loop_policy_does_not_reapply_same_power_mode_without_power_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.PERFORMANCE, ac_power_mode=PowerMode.BALANCED))
    second = policy.update(_inputs(now=1.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.BALANCED))

    assert ActivatePowerMode(PowerMode.BALANCED) in first.actions
    assert second.actions == ()


def test_power_source_loop_policy_retries_power_mode_when_active_mode_stays_wrong() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0, power_mode_retry_seconds=10.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    too_soon = policy.update(
        _inputs(now=5.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )
    retried = policy.update(
        _inputs(now=11.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert not any(isinstance(action, ActivatePowerMode) for action in too_soon.actions)
    assert ActivatePowerMode(PowerMode.PERFORMANCE) in retried.actions


def test_power_source_loop_policy_does_not_retry_successful_apply_when_observation_stays_wrong() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0, power_mode_retry_seconds=10.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    policy.record_power_mode_apply_result(PowerMode.PERFORMANCE, True)
    later = policy.update(_inputs(now=30.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert not any(isinstance(action, ActivatePowerMode) for action in later.actions)


def test_power_source_loop_policy_retries_failed_apply_after_delay() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0, power_mode_retry_seconds=10.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    policy.record_power_mode_apply_result(PowerMode.PERFORMANCE, False)
    too_soon = policy.update(
        _inputs(now=5.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )
    retried = policy.update(
        _inputs(now=11.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert not any(isinstance(action, ActivatePowerMode) for action in too_soon.actions)
    assert ActivatePowerMode(PowerMode.PERFORMANCE) in retried.actions


def test_power_source_loop_policy_reapplies_satisfied_mode_after_source_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0, power_mode_retry_seconds=10.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    policy.record_power_mode_apply_result(PowerMode.PERFORMANCE, True)
    same_source = policy.update(
        _inputs(now=1.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )
    changed_source = policy.update(
        _inputs(
            on_ac=False,
            now=2.0,
            active_power_mode=PowerMode.BALANCED,
            ac_power_mode=PowerMode.PERFORMANCE,
            battery_power_mode=PowerMode.PERFORMANCE,
        )
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert not any(isinstance(action, ActivatePowerMode) for action in same_source.actions)
    assert ActivatePowerMode(PowerMode.PERFORMANCE) in changed_source.actions


def test_power_source_loop_policy_reapplies_after_configured_mode_changes() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    policy.record_power_mode_apply_result(PowerMode.PERFORMANCE, True)
    changed = policy.update(
        _inputs(
            now=1.0,
            active_power_mode=PowerMode.PERFORMANCE,
            ac_power_mode=PowerMode.BALANCED,
        )
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert ActivatePowerMode(PowerMode.BALANCED) in changed.actions


def test_power_source_loop_policy_preserves_manual_power_mode_after_desired_mode_was_observed() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0, power_mode_retry_seconds=10.0)

    first = policy.update(_inputs(active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE))
    observed = policy.update(
        _inputs(now=1.0, active_power_mode=PowerMode.PERFORMANCE, ac_power_mode=PowerMode.PERFORMANCE)
    )
    manual_override = policy.update(
        _inputs(now=30.0, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.PERFORMANCE)
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in first.actions
    assert not any(isinstance(action, ActivatePowerMode) for action in observed.actions)
    assert not any(isinstance(action, ActivatePowerMode) for action in manual_override.actions)


def test_power_source_loop_policy_switches_to_battery_power_mode_on_transition() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(_inputs(active_power_mode=PowerMode.PERFORMANCE, ac_power_mode=PowerMode.BALANCED))
    res = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            active_power_mode=PowerMode.BALANCED,
            ac_power_mode=PowerMode.BALANCED,
            battery_power_mode=PowerMode.EXTREME_SAVER,
        )
    )

    assert ActivatePowerMode(PowerMode.EXTREME_SAVER) in res.actions


def test_power_source_loop_policy_switches_to_ac_power_mode_on_transition() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(
        _inputs(
            on_ac=False,
            active_power_mode=PowerMode.EXTREME_SAVER,
            ac_power_mode=PowerMode.PERFORMANCE,
            battery_power_mode=PowerMode.EXTREME_SAVER,
        )
    )
    res = policy.update(
        _inputs(
            on_ac=True,
            now=10.0,
            active_power_mode=PowerMode.EXTREME_SAVER,
            ac_power_mode=PowerMode.PERFORMANCE,
            battery_power_mode=PowerMode.EXTREME_SAVER,
        )
    )

    assert ActivatePowerMode(PowerMode.PERFORMANCE) in res.actions


def test_power_source_loop_policy_applies_power_mode_when_lighting_disabled_for_power_source() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(_inputs(on_ac=True, active_power_mode=PowerMode.PERFORMANCE, ac_power_mode=PowerMode.PERFORMANCE))
    res = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            active_power_mode=PowerMode.PERFORMANCE,
            battery_enabled=False,
            ac_power_mode=PowerMode.PERFORMANCE,
            battery_power_mode=PowerMode.EXTREME_SAVER,
        )
    )

    assert TurnOffKeyboard() in res.actions
    assert ActivatePowerMode(PowerMode.EXTREME_SAVER) in res.actions


def test_power_source_loop_policy_power_source_transition_reapplies_same_configured_power_mode() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(_inputs(on_ac=True, active_power_mode=PowerMode.BALANCED, ac_power_mode=PowerMode.BALANCED))
    manual_override = policy.update(
        _inputs(
            on_ac=True,
            now=5.0,
            active_power_mode=PowerMode.PERFORMANCE,
            ac_power_mode=PowerMode.BALANCED,
            battery_power_mode=PowerMode.BALANCED,
        )
    )
    battery_transition = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            active_power_mode=PowerMode.PERFORMANCE,
            ac_power_mode=PowerMode.BALANCED,
            battery_power_mode=PowerMode.BALANCED,
        )
    )

    assert not any(isinstance(action, ActivatePowerMode) for action in manual_override.actions)
    assert ActivatePowerMode(PowerMode.BALANCED) in battery_transition.actions


def test_power_source_loop_policy_activates_selected_perkey_profile_on_first_tick_when_needed() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(active_perkey_profile_name="movie", ac_perkey_profile_name="gaming"))

    assert ActivatePerkeyProfile("gaming") in res.actions


def test_power_source_loop_policy_does_not_reapply_same_perkey_profile_without_power_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    first = policy.update(_inputs(active_perkey_profile_name="movie", ac_perkey_profile_name="gaming"))
    second = policy.update(
        _inputs(
            now=1.0,
            active_perkey_profile_name="gaming",
            ac_perkey_profile_name="gaming",
        )
    )

    assert ActivatePerkeyProfile("gaming") in first.actions
    assert second.actions == ()


def test_power_source_loop_policy_switches_to_battery_perkey_profile_on_transition() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(_inputs(active_perkey_profile_name="movie", ac_perkey_profile_name="gaming"))
    res = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            active_perkey_profile_name="gaming",
            ac_perkey_profile_name="gaming",
            battery_perkey_profile_name="battery",
        )
    )

    assert ActivatePerkeyProfile("battery") in res.actions
