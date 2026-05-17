from __future__ import annotations

from src.core.power.policies.power_source_loop_policy import (
    ActivatePerkeyProfile,
    ActivatePowerMode,
    ApplyBrightness,
    PowerSourceLoopInputs,
    PowerSourceLoopPolicy,
    RestoreKeyboard,
    TurnOffKeyboard,
)
from src.core.power.system import PowerMode


def _inputs(**overrides) -> PowerSourceLoopInputs:
    values = {
        "on_ac": True,
        "now": 0.0,
        "power_management_enabled": True,
        "current_brightness": 50,
        "is_off": False,
        "active_power_mode": None,
        "active_perkey_profile_name": None,
        "ac_enabled": True,
        "battery_enabled": True,
        "ac_brightness_override": None,
        "battery_brightness_override": None,
        "ac_power_mode": None,
        "battery_power_mode": None,
        "ac_perkey_profile_name": None,
        "battery_perkey_profile_name": None,
        "battery_saver_enabled": False,
        "battery_saver_brightness": 25,
    }
    values.update(overrides)
    return PowerSourceLoopInputs(**values)


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


def test_power_source_loop_policy_applies_override_brightness_only_on_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(
        _inputs(
            ac_brightness_override=20,
        )
    )
    assert any(isinstance(a, ApplyBrightness) and a.brightness == 20 for a in res.actions)

    # Same override again -> should not re-emit ApplyBrightness.
    res2 = policy.update(
        _inputs(
            now=1.0,
            ac_brightness_override=20,
        )
    )
    assert not any(isinstance(a, ApplyBrightness) for a in res2.actions)


def test_power_source_loop_policy_skips_noop_initial_override_apply() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(current_brightness=20, ac_brightness_override=20))

    assert not any(isinstance(a, ApplyBrightness) for a in res.actions)


def test_power_source_loop_policy_legacy_battery_saver_dim_action() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    # Prime state.
    _ = policy.update(
        _inputs(
            battery_saver_enabled=True,
        )
    )

    # Transition to battery after enough time: expect dim to 25.
    res = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            battery_saver_enabled=True,
        )
    )

    assert any(isinstance(a, ApplyBrightness) and a.brightness == 25 for a in res.actions)


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
