from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IdleRestoreStartPolicy:
    brightness_override: Optional[int]
    fade_in: bool


def classify_idle_restore_start(
    config: object,
    *,
    soft_on_start_brightness: int,
) -> IdleRestoreStartPolicy:
    # Idle turn-off stops the effect thread and clears engine startup state, so
    # restore is a cold start even for loop effects.
    del config
    return IdleRestoreStartPolicy(brightness_override=int(soft_on_start_brightness), fade_in=True)
