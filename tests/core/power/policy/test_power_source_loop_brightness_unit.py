from __future__ import annotations

from keyrgb.core.power.policies.power_source_loop_policy import (
    ActivatePerkeyProfile,
    ApplyBrightness,
    PowerSourceLoopPolicy,
    TurnOffKeyboard,
)
from tests.core.power.policy._power_source_loop_support import make_inputs as _inputs


def test_power_source_loop_policy_applies_override_brightness_only_on_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(ac_brightness_override=20))
    assert any(isinstance(a, ApplyBrightness) and a.brightness == 20 for a in res.actions)

    # Same override again -> should not re-emit ApplyBrightness.
    res2 = policy.update(_inputs(now=1.0, ac_brightness_override=20))
    assert not any(isinstance(a, ApplyBrightness) for a in res2.actions)


def test_power_source_loop_policy_retries_brightness_suppressed_while_controller_dark() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    battery = policy.update(
        _inputs(
            on_ac=False,
            current_brightness=40,
            battery_brightness_override=10,
            battery_perkey_profile_name="battery",
        )
    )
    assert ApplyBrightness(10) in battery.actions

    # AC returns while controller-native sleep/wake settling still owns the
    # dark deck. The profile may activate, but brightness cannot be emitted.
    dark_ac = policy.update(
        _inputs(
            on_ac=True,
            now=1.0,
            current_brightness=10,
            is_off=True,
            ac_brightness_override=40,
            ac_perkey_profile_name="plugged-in",
            active_perkey_profile_name="battery",
        )
    )
    assert ActivatePerkeyProfile("plugged-in") in dark_ac.actions
    assert not any(isinstance(action, ApplyBrightness) for action in dark_ac.actions)

    # Once the deck is awake, the same desired value must be retried rather
    # than deduplicated as though the suppressed write had succeeded.
    awake_ac = policy.update(
        _inputs(
            on_ac=True,
            now=2.0,
            current_brightness=10,
            is_off=False,
            ac_brightness_override=40,
            ac_perkey_profile_name="plugged-in",
            active_perkey_profile_name="plugged-in",
        )
    )
    assert awake_ac.actions == (ApplyBrightness(40),)

    stable_ac = policy.update(
        _inputs(
            on_ac=True,
            now=3.0,
            current_brightness=40,
            ac_brightness_override=40,
            ac_perkey_profile_name="plugged-in",
            active_perkey_profile_name="plugged-in",
        )
    )
    assert stable_ac.actions == ()


def test_power_source_loop_policy_skips_noop_initial_override_apply() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(_inputs(current_brightness=20, ac_brightness_override=20))

    assert not any(isinstance(a, ApplyBrightness) for a in res.actions)


def test_power_source_loop_policy_reapplies_same_override_after_no_override_state() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    first = policy.update(_inputs(ac_brightness_override=20, current_brightness=50))
    no_override = policy.update(_inputs(now=1.0, ac_brightness_override=None, current_brightness=35))
    reapplied = policy.update(_inputs(now=2.0, ac_brightness_override=20, current_brightness=35))

    assert ApplyBrightness(20) in first.actions
    assert not any(isinstance(a, ApplyBrightness) for a in no_override.actions)
    assert ApplyBrightness(20) in reapplied.actions


def test_power_source_loop_policy_reapplies_same_override_after_disabled_state() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    first = policy.update(_inputs(ac_brightness_override=20, current_brightness=50))
    disabled = policy.update(_inputs(now=1.0, ac_enabled=False, ac_brightness_override=20, current_brightness=20))
    restored = policy.update(_inputs(now=2.0, ac_brightness_override=20, current_brightness=35))

    assert ApplyBrightness(20) in first.actions
    assert any(isinstance(a, TurnOffKeyboard) for a in disabled.actions)
    assert ApplyBrightness(20) in restored.actions


def test_power_source_loop_policy_legacy_battery_saver_dim_action() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    _ = policy.update(_inputs(battery_saver_enabled=True))
    res = policy.update(
        _inputs(
            on_ac=False,
            now=10.0,
            battery_saver_enabled=True,
        )
    )

    assert any(isinstance(a, ApplyBrightness) and a.brightness == 25 for a in res.actions)
