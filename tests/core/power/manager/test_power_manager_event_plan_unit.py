from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.power.management._manager_power_events import (
    PowerEventExecutionPlan,
    build_power_event_execution_plan,
    build_power_event_inputs,
    execute_power_event_plan,
    invoke_keyboard_method,
)


class _ExpectedAction:
    pass


class _OtherAction:
    pass


def test_build_power_event_inputs_bool_coerces_all_fields() -> None:
    inputs = build_power_event_inputs(enabled=1, action_enabled="", is_off="yes")

    assert inputs.enabled is True
    assert inputs.action_enabled is False
    assert inputs.is_off is True


def test_build_power_event_execution_plan_no_actions_returns_noop_plan() -> None:
    plan = build_power_event_execution_plan(
        result=SimpleNamespace(actions=[]),
        expected_action_type=_ExpectedAction,
        action_enabled=True,
        delay_s=0.5,
    )

    assert plan.action_count == 0
    assert plan.should_log is False
    assert plan.delay_s == 0.0
    assert plan.should_invoke is False


def test_build_power_event_execution_plan_filters_action_type() -> None:
    plan = build_power_event_execution_plan(
        result=SimpleNamespace(actions=[_OtherAction(), _ExpectedAction(), _ExpectedAction()]),
        expected_action_type=_ExpectedAction,
        action_enabled=True,
        delay_s=0.2,
    )

    assert plan.action_count == 2
    assert plan.should_log is True
    assert plan.delay_s == pytest.approx(0.2)
    assert plan.should_invoke is True


def test_build_power_event_execution_plan_disables_when_action_not_enabled() -> None:
    plan = build_power_event_execution_plan(
        result=SimpleNamespace(actions=[_ExpectedAction()]),
        expected_action_type=_ExpectedAction,
        action_enabled=False,
        delay_s=1.0,
    )

    assert plan.action_count == 0
    assert plan.should_log is False
    assert plan.delay_s == 0.0
    assert plan.should_invoke is False


@pytest.mark.parametrize("delay_s", [0, -0.25])
def test_build_power_event_execution_plan_non_positive_delay_is_zero(delay_s: float) -> None:
    plan = build_power_event_execution_plan(
        result=SimpleNamespace(actions=[_ExpectedAction()]),
        expected_action_type=_ExpectedAction,
        action_enabled=True,
        delay_s=delay_s,
    )

    assert plan.action_count == 1
    assert plan.should_log is True
    assert plan.delay_s == 0.0


def test_power_event_execution_plan_should_invoke_depends_on_action_count() -> None:
    assert PowerEventExecutionPlan(action_count=0, should_log=False, delay_s=0.0).should_invoke is False
    assert PowerEventExecutionPlan(action_count=1, should_log=True, delay_s=0.1).should_invoke is True


def test_execute_power_event_plan_logs_sleeps_once_and_invokes_per_action_count() -> None:
    log_info = MagicMock()
    sleep = MagicMock()
    invoke = MagicMock()

    execute_power_event_plan(
        plan=PowerEventExecutionPlan(action_count=2, should_log=True, delay_s=0.25),
        log_message="hello",
        kb_method_name="turn_off",
        log_info_fn=log_info,
        sleep_fn=sleep,
        invoke_keyboard_method_fn=invoke,
    )

    log_info.assert_called_once_with("hello")
    sleep.assert_called_once_with(0.25)
    assert invoke.call_count == 2
    invoke.assert_called_with("turn_off")


def test_execute_power_event_plan_noop_plan_skips_side_effects() -> None:
    log_info = MagicMock()
    sleep = MagicMock()
    invoke = MagicMock()

    execute_power_event_plan(
        plan=PowerEventExecutionPlan(action_count=0, should_log=False, delay_s=1.0),
        log_message="ignored",
        kb_method_name="restore",
        log_info_fn=log_info,
        sleep_fn=sleep,
        invoke_keyboard_method_fn=invoke,
    )

    log_info.assert_not_called()
    sleep.assert_not_called()
    invoke.assert_not_called()


def test_invoke_keyboard_method_runs_callable_method_inside_runtime_boundary() -> None:
    kb = MagicMock()
    kb.turn_off = MagicMock()

    captured = {}

    def _run_boundary(action, *, log_message: str, fallback=None):
        captured["log_message"] = log_message
        return action()

    invoke_keyboard_method(
        kb_controller=kb,
        method_name="turn_off",
        run_recoverable_runtime_boundary_fn=_run_boundary,
    )

    kb.turn_off.assert_called_once()
    assert captured["log_message"] == "Power event keyboard action 'turn_off' failed"
