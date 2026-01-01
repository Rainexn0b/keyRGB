from __future__ import annotations

from src.core.power_policies.power_source_loop_policy import (
    ApplyBrightness,
    PowerSourceLoopInputs,
    PowerSourceLoopPolicy,
    RestoreKeyboard,
    TurnOffKeyboard,
)


def test_power_source_loop_policy_debounces_power_flapping() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=3.0)

    first = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=0.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert first.skip is False

    flapping = policy.update(
        PowerSourceLoopInputs(
            on_ac=False,
            now=1.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert flapping.skip is True
    assert flapping.actions == ()


def test_power_source_loop_policy_emits_enable_disable_actions() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    # First tick on AC, AC disabled -> should request turn off.
    res = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=0.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=False,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert any(isinstance(a, TurnOffKeyboard) for a in res.actions)

    # Now enable AC lighting -> should request restore.
    res2 = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=10.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert any(isinstance(a, RestoreKeyboard) for a in res2.actions)


def test_power_source_loop_policy_applies_override_brightness_only_on_change() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    res = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=0.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=20,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert any(isinstance(a, ApplyBrightness) and a.brightness == 20 for a in res.actions)

    # Same override again -> should not re-emit ApplyBrightness.
    res2 = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=1.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=20,
            battery_brightness_override=None,
            battery_saver_enabled=False,
            battery_saver_brightness=25,
        )
    )
    assert not any(isinstance(a, ApplyBrightness) for a in res2.actions)


def test_power_source_loop_policy_legacy_battery_saver_dim_action() -> None:
    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)

    # Prime state.
    _ = policy.update(
        PowerSourceLoopInputs(
            on_ac=True,
            now=0.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=True,
            battery_saver_brightness=25,
        )
    )

    # Transition to battery after enough time: expect dim to 25.
    res = policy.update(
        PowerSourceLoopInputs(
            on_ac=False,
            now=10.0,
            power_management_enabled=True,
            current_brightness=50,
            is_off=False,
            ac_enabled=True,
            battery_enabled=True,
            ac_brightness_override=None,
            battery_brightness_override=None,
            battery_saver_enabled=True,
            battery_saver_brightness=25,
        )
    )

    assert any(isinstance(a, ApplyBrightness) and a.brightness == 25 for a in res.actions)
