"""Pure unit tests for idle-power power-source guard decisions."""

from __future__ import annotations

from src.tray.pollers.idle_power._power_source_guard import (
    plan_power_source_guard_update,
    power_source_idle_guard_active,
)


def test_power_source_idle_guard_active_window() -> None:
    assert power_source_idle_guard_active(
        now=10.0,
        last_power_source_change_at=9.0,
        suppression_s=2.0,
    )
    assert not power_source_idle_guard_active(
        now=12.0,
        last_power_source_change_at=9.0,
        suppression_s=2.0,
    )
    assert not power_source_idle_guard_active(
        now=10.0,
        last_power_source_change_at=0.0,
        suppression_s=2.0,
    )


def test_plan_power_source_guard_update_seeds_first_reading() -> None:
    plan = plan_power_source_guard_update(
        on_ac_power=True,
        last_on_ac_power=None,
        last_power_source_change_at=0.0,
        now=100.0,
    )
    assert plan is not None
    assert plan.last_on_ac_power is True
    assert plan.last_power_source_change_at == 0.0
    assert plan.reset_sensitive_idle_state is False


def test_plan_power_source_guard_update_ignores_unknown() -> None:
    assert (
        plan_power_source_guard_update(
            on_ac_power=None,
            last_on_ac_power=True,
            last_power_source_change_at=1.0,
            now=2.0,
        )
        is None
    )


def test_plan_power_source_guard_update_transition_resets() -> None:
    plan = plan_power_source_guard_update(
        on_ac_power=False,
        last_on_ac_power=True,
        last_power_source_change_at=1.0,
        now=50.0,
    )
    assert plan is not None
    assert plan.last_on_ac_power is False
    assert plan.last_power_source_change_at == 50.0
    assert plan.reset_sensitive_idle_state is True


def test_plan_power_source_guard_update_stable_no_reset() -> None:
    plan = plan_power_source_guard_update(
        on_ac_power=True,
        last_on_ac_power=True,
        last_power_source_change_at=7.0,
        now=9.0,
    )
    assert plan is not None
    assert plan.last_on_ac_power is True
    assert plan.last_power_source_change_at == 7.0
    assert plan.reset_sensitive_idle_state is False
