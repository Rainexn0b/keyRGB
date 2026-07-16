from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from .core import ConfigApplyState


ApplyExecutionKind = Literal["turn_off", "apply"]
ApplyMode = Literal["perkey", "uniform", "effect"]


@dataclass(frozen=True)
class ConfigApplyPlan:
    persist_effect: str | None
    execution_kind: ApplyExecutionKind
    apply_mode: ApplyMode = "effect"


def classify_apply_mode(effect: str) -> ApplyMode:
    """Pure classification of how a non-off config apply should drive the device."""

    if effect == "perkey":
        return "perkey"
    if effect == "none":
        return "uniform"
    return "effect"


def classify_config_apply_plan(*, configured_effect: str, current: ConfigApplyState) -> ConfigApplyPlan:
    target_effect = current.selected_effect or current.effect
    persist_effect = target_effect if configured_effect != target_effect else None
    if current.brightness == 0:
        return ConfigApplyPlan(
            persist_effect=persist_effect,
            execution_kind="turn_off",
            apply_mode=classify_apply_mode(current.effect),
        )
    return ConfigApplyPlan(
        persist_effect=persist_effect,
        execution_kind="apply",
        apply_mode=classify_apply_mode(current.effect),
    )


def should_skip_config_apply_for_power_source_transition(
    *,
    cause: str,
    current: ConfigApplyState,
    recent_power_source_transition: bool,
) -> bool:
    """Pure gate: suppress per-key mtime applies briefly after AC/battery profile swaps."""

    if not recent_power_source_transition:
        return False
    if str(cause or "") != "mtime_change":
        return False
    return current.perkey_sig is not None
