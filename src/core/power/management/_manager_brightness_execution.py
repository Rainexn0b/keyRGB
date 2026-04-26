from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class _BrightnessEngine(Protocol):
    def set_brightness(self, brightness: int) -> None: ...


@dataclass(frozen=True)
class BrightnessExecutionPlan:
    brightness: int
    controller_apply_fn: Callable[[int], None] | None = None
    engine: _BrightnessEngine | None = None

    @property
    def should_execute(self) -> bool:
        return self.controller_apply_fn is not None or self.engine is not None


def classify_brightness_execution(*, kb_controller, brightness: int) -> BrightnessExecutionPlan:
    apply_fn = getattr(kb_controller, "apply_brightness_from_power_policy", None)
    if callable(apply_fn):
        return BrightnessExecutionPlan(brightness=brightness, controller_apply_fn=apply_fn)

    engine = getattr(kb_controller, "engine", None)
    if engine is None:
        return BrightnessExecutionPlan(brightness=brightness)

    return BrightnessExecutionPlan(brightness=brightness, engine=engine)


def execute_brightness_execution(
    *,
    plan: BrightnessExecutionPlan,
    sync_config_brightness_fn: Callable[[int], None],
) -> None:
    if plan.controller_apply_fn is not None:
        plan.controller_apply_fn(plan.brightness)
        return

    if plan.engine is None:
        return

    sync_config_brightness_fn(plan.brightness)
    plan.engine.set_brightness(plan.brightness)


def apply_brightness_policy(
    kb_controller,
    brightness: int,
    *,
    run_boundary_fn,
    sync_config_fn,
) -> None:
    """Apply a power-policy brightness change, guarded by a recoverable runtime boundary."""
    if brightness < 0:
        return

    brightness = int(brightness)

    def _apply() -> None:
        plan = classify_brightness_execution(kb_controller=kb_controller, brightness=brightness)
        execute_brightness_execution(plan=plan, sync_config_brightness_fn=sync_config_fn)

    run_boundary_fn(_apply, log_message="Battery saver brightness apply failed")


def sync_config_brightness(
    config,
    brightness: int,
    *,
    logger,
) -> None:
    """Mirror a power-policy brightness value into config, ignoring expected setter errors."""
    try:
        config.brightness = brightness
    except (AttributeError, TypeError, ValueError, RuntimeError):
        logger.warning("Failed to mirror power-policy brightness into config", exc_info=True)
