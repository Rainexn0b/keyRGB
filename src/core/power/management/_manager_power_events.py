from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..policies.power_event_policy import PowerEventInputs


@dataclass(frozen=True)
class PowerEventExecutionPlan:
    action_count: int
    should_log: bool
    delay_s: float

    @property
    def should_invoke(self) -> bool:
        return self.action_count > 0


def build_power_event_inputs(*, enabled: bool, action_enabled: bool, is_off: bool) -> PowerEventInputs:
    return PowerEventInputs(
        enabled=bool(enabled),
        action_enabled=bool(action_enabled),
        is_off=bool(is_off),
    )


def build_power_event_execution_plan(
    *,
    result: object,
    expected_action_type: type[object],
    action_enabled: bool,
    delay_s: float,
) -> PowerEventExecutionPlan:
    action_count = 0
    for action in getattr(result, "actions", ()) or ():
        if isinstance(action, expected_action_type):
            action_count += 1

    if not bool(action_enabled) or action_count == 0:
        return PowerEventExecutionPlan(action_count=0, should_log=False, delay_s=0.0)

    return PowerEventExecutionPlan(
        action_count=action_count,
        should_log=True,
        delay_s=float(delay_s) if delay_s > 0 else 0.0,
    )


def orchestrate_power_event(
    *,
    enabled: bool,
    action_enabled: bool,
    delay_s: float,
    policy_method,
    expected_action_type: type[object],
    evaluate_policy_fn,
    execute_plan_fn,
) -> None:
    if not enabled:
        return

    result = evaluate_policy_fn(
        enabled=enabled,
        action_enabled=action_enabled,
        policy_method=policy_method,
    )
    if result is None:
        return

    plan = build_power_event_execution_plan(
        result=result,
        expected_action_type=expected_action_type,
        action_enabled=action_enabled,
        delay_s=delay_s,
    )
    execute_plan_fn(plan)


def execute_power_event_plan(
    *,
    plan: PowerEventExecutionPlan,
    log_message: str,
    kb_method_name: str,
    log_info_fn: Callable[[str], None],
    sleep_fn: Callable[[float], None],
    invoke_keyboard_method_fn: Callable[[str], None],
) -> None:
    if not plan.should_invoke:
        return

    if plan.should_log:
        log_info_fn(log_message)

    if plan.delay_s > 0:
        sleep_fn(plan.delay_s)

    for _ in range(plan.action_count):
        invoke_keyboard_method_fn(kb_method_name)


def invoke_keyboard_method(
    *,
    kb_controller,
    method_name: str,
    run_recoverable_runtime_boundary_fn,
) -> None:
    def _invoke() -> None:
        fn = getattr(kb_controller, method_name, None)
        if callable(fn):
            fn()

    run_recoverable_runtime_boundary_fn(
        _invoke,
        log_message=f"Power event keyboard action '{method_name}' failed",
    )