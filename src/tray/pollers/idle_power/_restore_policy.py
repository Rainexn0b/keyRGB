from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET, strip_effect_namespace
from src.core.utils.safe_attrs import safe_str_attr


@dataclass(frozen=True)
class IdleRestoreStartPolicy:
    brightness_override: Optional[int]
    fade_in: bool


def classify_idle_restore_start(
    config: object,
    *,
    soft_on_start_brightness: int,
) -> IdleRestoreStartPolicy:
    if _is_loop_effect_restore(config):
        return IdleRestoreStartPolicy(brightness_override=None, fade_in=False)

    return IdleRestoreStartPolicy(brightness_override=int(soft_on_start_brightness), fade_in=True)


def _is_loop_effect_restore(config: object) -> bool:
    try:
        effect_name = safe_str_attr(config, "effect", default="none") or "none"
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False

    normalized = strip_effect_namespace(effect_name)
    return bool(normalized in SW_EFFECTS_SET or normalized in REACTIVE_EFFECTS)