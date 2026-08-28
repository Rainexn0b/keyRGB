"""Package-owned software/reactive effect registration markers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal


class EffectKind(str, Enum):
    SOFTWARE = "software"
    REACTIVE = "reactive"


CURRENT_COLOR: Final = "current"
StartColor = Literal["current"] | tuple[int, int, int]


@dataclass(frozen=True)
class EffectRegistration:
    """Module-owned built-in effect registration marker.

    Implementation modules export ``EFFECT_REGISTRATION`` or
    ``EFFECT_REGISTRATIONS``. The effects registry discovers those markers and
    derives catalog names, titles, and engine start dispatch from them.
    Unmarked runners are not selectable.
    """

    name: str
    kind: EffectKind
    runner: Callable[..., None]
    start_color: StartColor = CURRENT_COLOR
    title: str | None = None
    menu_order: int = 0
