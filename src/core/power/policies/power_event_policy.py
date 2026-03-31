from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class TurnOffKeyboard:
    pass


@dataclass(frozen=True)
class RestoreKeyboard:
    pass


PowerEventAction = Union[TurnOffKeyboard, RestoreKeyboard]


@dataclass(frozen=True)
class PowerEventInputs:
    enabled: bool
    action_enabled: bool
    is_off: bool


@dataclass(frozen=True)
class PowerEventResult:
    actions: tuple[PowerEventAction, ...]


class PowerEventPolicy:
    """State machine for lid/suspend save+restore behavior.

    This is the behavior behind:
    - lid close/open
    - suspend/resume

    It is IO-free and unit-testable.
    """

    def __init__(self) -> None:
        self._saved_was_off: Optional[bool] = None

    def handle_power_off_event(self, inputs: PowerEventInputs) -> PowerEventResult:
        # Even if the action is disabled ("don't turn off on suspend"), we still
        # want to remember whether the keyboard was already off so we can decide
        # whether to restore on the matching resume/open event.
        if not bool(inputs.enabled):
            return PowerEventResult(actions=())

        if self._saved_was_off is None:
            self._saved_was_off = bool(inputs.is_off)

        if not bool(inputs.action_enabled):
            return PowerEventResult(actions=())

        return PowerEventResult(actions=(TurnOffKeyboard(),))

    def handle_power_restore_event(self, inputs: PowerEventInputs) -> PowerEventResult:
        if not bool(inputs.enabled):
            return PowerEventResult(actions=())

        if self._saved_was_off is None:
            return PowerEventResult(actions=())

        saved_was_off = bool(self._saved_was_off)
        self._saved_was_off = None

        if saved_was_off:
            return PowerEventResult(actions=())

        if not bool(inputs.action_enabled):
            return PowerEventResult(actions=())

        return PowerEventResult(actions=(RestoreKeyboard(),))
