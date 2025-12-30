from __future__ import annotations

from src.tray.idle_power_polling import _compute_idle_action


def test_dimmed_turns_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "turn_off"
    )


def test_dim_sync_does_not_act_when_disabled_or_zero_brightness() -> None:
    assert (
        _compute_idle_action(
            dimmed=True,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            power_management_enabled=False,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )

    assert (
        _compute_idle_action(
            dimmed=True,
            idle_timeout_s=60.0,
            is_off=False,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=0,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )


def test_restore_when_not_dimmed_and_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "restore"
    )


def test_restore_when_dim_unknown_and_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=None,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        == "restore"
    )


def test_idle_unknown_does_not_restore_if_idle_forced_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=None,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=True,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=False,
            power_forced_off=False,
        )
        is None
    )


def test_idle_never_fights_user_or_power_forced_off() -> None:
    assert (
        _compute_idle_action(
            dimmed=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=True,
            power_forced_off=False,
        )
        is None
    )

    assert (
        _compute_idle_action(
            dimmed=False,
            idle_timeout_s=60.0,
            is_off=True,
            idle_forced_off=False,
            power_management_enabled=True,
            brightness=25,
            user_forced_off=False,
            power_forced_off=True,
        )
        is None
    )
