from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from .core import ConfigApplyState


ApplyExecutionKind = Literal["turn_off", "apply"]


@dataclass(frozen=True)
class ConfigApplyPlan:
    persist_effect: str | None
    execution_kind: ApplyExecutionKind


def classify_config_apply_plan(*, configured_effect: str, current: ConfigApplyState) -> ConfigApplyPlan:
    persist_effect = current.effect if configured_effect != current.effect else None
    execution_kind: ApplyExecutionKind = "turn_off" if current.brightness == 0 else "apply"
    return ConfigApplyPlan(persist_effect=persist_effect, execution_kind=execution_kind)