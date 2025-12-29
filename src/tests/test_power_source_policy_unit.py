from __future__ import annotations

from src.core.power_source_policy import compute_power_source_policy


def test_policy_selects_enabled_flag_by_power_source() -> None:
    enabled, brightness = compute_power_source_policy(
        on_ac=True,
        ac_enabled=False,
        battery_enabled=True,
        ac_brightness_override=None,
        battery_brightness_override=None,
    )
    assert enabled is False
    assert brightness is None

    enabled, brightness = compute_power_source_policy(
        on_ac=False,
        ac_enabled=False,
        battery_enabled=True,
        ac_brightness_override=None,
        battery_brightness_override=None,
    )
    assert enabled is True
    assert brightness is None


def test_policy_parses_and_clamps_brightness_overrides() -> None:
    enabled, brightness = compute_power_source_policy(
        on_ac=True,
        ac_enabled=True,
        battery_enabled=True,
        ac_brightness_override="60",
        battery_brightness_override=None,
    )
    assert enabled is True
    assert brightness == 50

    enabled, brightness = compute_power_source_policy(
        on_ac=False,
        ac_enabled=True,
        battery_enabled=True,
        ac_brightness_override=None,
        battery_brightness_override=-5,
    )
    assert enabled is True
    assert brightness == 0

    enabled, brightness = compute_power_source_policy(
        on_ac=False,
        ac_enabled=True,
        battery_enabled=True,
        ac_brightness_override=None,
        battery_brightness_override="12.7",
    )
    assert brightness == 12


def test_policy_ignores_unparseable_override() -> None:
    enabled, brightness = compute_power_source_policy(
        on_ac=True,
        ac_enabled=True,
        battery_enabled=True,
        ac_brightness_override="nope",
        battery_brightness_override=None,
    )
    assert enabled is True
    assert brightness is None
