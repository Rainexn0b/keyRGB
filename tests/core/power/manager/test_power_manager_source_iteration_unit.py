from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.core.power.management._manager_source_iteration import (
    IterationDisposition,
    classify_power_source_iteration,
)


def test_classify_power_source_iteration_sleeps_when_power_source_unknown() -> None:
    build_inputs = MagicMock()
    policy = MagicMock()

    plan = classify_power_source_iteration(
        raw_on_ac=None,
        build_loop_inputs_fn=build_inputs,
        policy=policy,
    )

    assert plan.disposition is IterationDisposition.SLEEP
    assert plan.should_sleep is True
    assert plan.actions == ()
    build_inputs.assert_not_called()
    policy.update.assert_not_called()


def test_classify_power_source_iteration_sleeps_when_inputs_are_unavailable() -> None:
    build_inputs = MagicMock(return_value=None)
    policy = MagicMock()

    plan = classify_power_source_iteration(
        raw_on_ac=True,
        build_loop_inputs_fn=build_inputs,
        policy=policy,
    )

    assert plan.disposition is IterationDisposition.SLEEP
    assert plan.should_sleep is True
    assert plan.actions == ()
    build_inputs.assert_called_once_with(True)
    policy.update.assert_not_called()


def test_classify_power_source_iteration_sleeps_when_policy_skips() -> None:
    loop_inputs = object()
    build_inputs = MagicMock(return_value=loop_inputs)
    policy = MagicMock()
    policy.update.return_value = SimpleNamespace(skip=True, actions=("ignored",))

    plan = classify_power_source_iteration(
        raw_on_ac=True,
        build_loop_inputs_fn=build_inputs,
        policy=policy,
    )

    assert plan.disposition is IterationDisposition.SLEEP
    assert plan.should_sleep is True
    assert plan.actions == ()
    policy.update.assert_called_once_with(loop_inputs)


def test_classify_power_source_iteration_applies_actions_when_policy_returns_actions() -> None:
    loop_inputs = object()
    build_inputs = MagicMock(return_value=loop_inputs)
    policy = MagicMock()
    action_1 = object()
    action_2 = object()
    policy.update.return_value = SimpleNamespace(skip=False, actions=[action_1, action_2])

    plan = classify_power_source_iteration(
        raw_on_ac=True,
        build_loop_inputs_fn=build_inputs,
        policy=policy,
    )

    assert plan.disposition is IterationDisposition.APPLY_ACTIONS
    assert plan.should_sleep is False
    assert plan.actions == (action_1, action_2)
    policy.update.assert_called_once_with(loop_inputs)


def test_classify_power_source_iteration_coerces_non_bool_on_ac_to_bool() -> None:
    build_inputs = MagicMock(return_value=object())
    policy = MagicMock(return_value=SimpleNamespace(skip=False, actions=()))
    policy.update.return_value = SimpleNamespace(skip=False, actions=())

    classify_power_source_iteration(
        raw_on_ac=1,
        build_loop_inputs_fn=build_inputs,
        policy=policy,
    )

    build_inputs.assert_called_once_with(True)
