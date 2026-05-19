from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from src.core.effects.catalog import REACTIVE_EFFECTS, normalize_effect_name, strip_effect_namespace
from src.core.lighting_layers import render_effect_from_selected_effect


class _BrightnessEngine(Protocol):
    def set_brightness(self, brightness: int) -> None: ...


@dataclass(frozen=True)
class BrightnessExecutionPlan:
    brightness: int
    controller_apply_fn: Callable[[int], None] | None = None
    engine: _BrightnessEngine | None = None
    sync_engine_perkey_brightness: bool = False

    @property
    def should_execute(self) -> bool:
        return self.controller_apply_fn is not None or self.engine is not None


_BRIGHTNESS_STATE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _config_selected_effect(config: object) -> str:
    try:
        return normalize_effect_name(str(getattr(config, "effect", "none") or "none")) or "none"
    except _BRIGHTNESS_STATE_EXCEPTIONS:
        return "none"


def _config_render_effect(config: object) -> str:
    try:
        per_key_colors = getattr(config, "per_key_colors", None)
    except _BRIGHTNESS_STATE_EXCEPTIONS:
        per_key_colors = None
    return render_effect_from_selected_effect(
        selected_effect=_config_selected_effect(config),
        per_key_colors=per_key_colors,
    )


def _should_sync_perkey_brightness(config: object | None) -> bool:
    if config is None:
        return False

    render_effect = _config_render_effect(config)
    if render_effect == "perkey":
        return True

    return strip_effect_namespace(_config_selected_effect(config)) in frozenset(REACTIVE_EFFECTS)


def classify_brightness_execution(
    *, kb_controller, brightness: int, config: object | None = None
) -> BrightnessExecutionPlan:
    apply_fn = getattr(kb_controller, "apply_brightness_from_power_policy", None)
    if callable(apply_fn):
        return BrightnessExecutionPlan(brightness=brightness, controller_apply_fn=apply_fn)

    engine = getattr(kb_controller, "engine", None)
    if engine is None:
        return BrightnessExecutionPlan(brightness=brightness)

    return BrightnessExecutionPlan(
        brightness=brightness,
        engine=engine,
        sync_engine_perkey_brightness=_should_sync_perkey_brightness(config),
    )


def execute_brightness_execution(
    *,
    plan: BrightnessExecutionPlan,
    sync_config_brightness_fn: Callable[[int], int | None],
) -> None:
    if plan.controller_apply_fn is not None:
        plan.controller_apply_fn(plan.brightness)
        return

    if plan.engine is None:
        return

    effective_brightness_raw = sync_config_brightness_fn(plan.brightness)
    if isinstance(effective_brightness_raw, bool):
        effective_brightness = int(plan.brightness)
    elif isinstance(effective_brightness_raw, (int, float)):
        effective_brightness = int(effective_brightness_raw)
    elif isinstance(effective_brightness_raw, str):
        try:
            effective_brightness = int(effective_brightness_raw.strip())
        except (TypeError, ValueError, OverflowError):
            effective_brightness = int(plan.brightness)
    else:
        effective_brightness = int(plan.brightness)
    if plan.sync_engine_perkey_brightness:
        try:
            plan.engine.per_key_brightness = int(effective_brightness)  # type: ignore[attr-defined]
        except _BRIGHTNESS_STATE_EXCEPTIONS:
            pass
    plan.engine.set_brightness(int(effective_brightness))


def apply_brightness_policy(
    kb_controller,
    brightness: int,
    *,
    run_boundary_fn,
    config,
    sync_config_fn: Callable[[int], int | None],
) -> None:
    """Apply a power-policy brightness change, guarded by a recoverable runtime boundary."""
    if brightness < 0:
        return

    brightness = int(brightness)

    def _apply() -> None:
        plan = classify_brightness_execution(kb_controller=kb_controller, brightness=brightness, config=config)
        execute_brightness_execution(plan=plan, sync_config_brightness_fn=sync_config_fn)

    run_boundary_fn(_apply, log_message="Battery saver brightness apply failed")


def sync_config_brightness(
    config,
    brightness: int,
    *,
    logger,
) -> int:
    """Mirror a power-policy brightness value into config, ignoring expected setter errors."""

    requested = int(brightness)
    effective = requested
    global_synced = False

    try:
        setattr(config, "effect_brightness", requested)
        global_synced = True
        try:
            effective = int(getattr(config, "effect_brightness"))
        except _BRIGHTNESS_STATE_EXCEPTIONS:
            effective = requested
    except AttributeError:
        pass
    except (TypeError, ValueError, RuntimeError):
        logger.warning("Failed to mirror power-policy effect brightness into config", exc_info=True)

    try:
        if not global_synced:
            config.brightness = requested
            global_synced = True
            try:
                effective = int(getattr(config, "brightness"))
            except _BRIGHTNESS_STATE_EXCEPTIONS:
                effective = requested
        if _should_sync_perkey_brightness(config):
            config.perkey_brightness = effective
    except (AttributeError, TypeError, ValueError, RuntimeError):
        logger.warning("Failed to mirror power-policy brightness into config", exc_info=True)
    return effective
