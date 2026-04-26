from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from ..policies.power_source_loop_policy import PowerAction, PowerSourceLoopInputs


class IterationDisposition(str, Enum):
    SLEEP = "sleep"
    APPLY_ACTIONS = "apply_actions"


@dataclass(frozen=True)
class PowerSourceIterationPlan:
    disposition: IterationDisposition
    actions: tuple[PowerAction, ...]

    @property
    def should_sleep(self) -> bool:
        return self.disposition is IterationDisposition.SLEEP


class SupportsPowerSourceLoopPolicy(Protocol):
    def update(self, inputs: PowerSourceLoopInputs): ...


BuildLoopInputsFn = Callable[[bool], PowerSourceLoopInputs | None]


def classify_power_source_iteration(
    *,
    raw_on_ac: bool | None,
    build_loop_inputs_fn: BuildLoopInputsFn,
    policy: SupportsPowerSourceLoopPolicy,
) -> PowerSourceIterationPlan:
    if raw_on_ac is None:
        return PowerSourceIterationPlan(disposition=IterationDisposition.SLEEP, actions=())

    loop_inputs = build_loop_inputs_fn(bool(raw_on_ac))
    if loop_inputs is None:
        return PowerSourceIterationPlan(disposition=IterationDisposition.SLEEP, actions=())

    result = policy.update(loop_inputs)
    if bool(getattr(result, "skip", False)):
        return PowerSourceIterationPlan(disposition=IterationDisposition.SLEEP, actions=())

    return PowerSourceIterationPlan(
        disposition=IterationDisposition.APPLY_ACTIONS,
        actions=tuple(getattr(result, "actions", ()) or ()),
    )
