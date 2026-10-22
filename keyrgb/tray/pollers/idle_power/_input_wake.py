"""Opt-in input wake evidence; hardware execution stays in DeckPipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from keyrgb.core.utils.safe_attrs import safe_bool_attr
from keyrgb.tray.controllers.runtime_coordination import run_tray_observation_if_current
from keyrgb.tray.deck_state import DeckState, SleepWakeIntent, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import read_idle_power_state_bool_field, read_idle_power_state_float_field
from keyrgb.tray.protocols import IdlePowerTrayProtocol

from ._constants import WAYLAND_IDLE_RECONNECT_BACKOFF_S
from ._input_idle import InputIdleTracker

if TYPE_CHECKING:
    from ._runtime import IdlePollLoopState

logger = logging.getLogger(__name__)
_INPUT_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


@dataclass
class InputWakeState:
    """A short-lived, input-only compositor listener for one dark epoch."""

    epoch: tuple[DeckState, float] | None = None
    tracker: object | None = None
    retry_at: float = 0.0
    wake_not_before: float = 0.0

    def close(self) -> None:
        tracker, self.tracker = self.tracker, None
        self.epoch = None
        self.retry_at = 0.0
        self.wake_not_before = 0.0
        close = getattr(tracker, "close", None)
        if callable(close):
            try:
                close()
            except _INPUT_ERRORS:
                logger.debug("Unable to close input wake listener", exc_info=True)

    def prepare(self, epoch: tuple[DeckState, float]) -> None:
        if self.epoch != epoch:
            self.close()
            self.epoch = epoch

    def activity_at(
        self,
        *,
        epoch: tuple[DeckState, float],
        now: float,
        create: Callable[[int], object | None],
        read: Callable[[object], bool | None],
    ) -> float:
        self.prepare(epoch)
        if self.tracker is None and now < self.retry_at:
            return 0.0
        try:
            if self.tracker is None:
                # Separate from screen-dim timing. Initial active state and a
                # reconnect are not input; only an idled -> resumed callback is.
                self.tracker = create(0)
            if self.tracker is not None and read(self.tracker) is not None:
                return float(getattr(self.tracker, "last_activity_at", 0.0))
        except _INPUT_ERRORS:
            logger.debug("Input wake listener unavailable", exc_info=True)
        self.close()
        self.epoch = epoch
        self.retry_at = now + WAYLAND_IDLE_RECONNECT_BACKOFF_S
        return 0.0


@dataclass(frozen=True)
class InputWakeEvidence:
    state: DeckState
    sleep_at: float
    activity_at: float


def wake_on_any_input_enabled(tray: IdlePowerTrayProtocol) -> bool:
    return safe_bool_attr(tray.config, "controller_sleep_respect", default=False) and safe_bool_attr(
        tray.config, "wake_on_any_input", default=False
    )


def _sleep_at(tray: IdlePowerTrayProtocol) -> float:
    # Both causes can survive a failed restore. Input must follow the newest
    # active off, not merely the controller's earlier sleep observation.
    timestamps = [0.0]
    for cause, field in (
        ("controller_sleep_off", "controller_sleep_off_at"),
        ("idle_forced_off", "last_idle_turn_off_at"),
    ):
        if read_idle_power_state_bool_field(tray, attr_name=f"_{cause}", state_name=cause, default=False):
            timestamps.append(
                read_idle_power_state_float_field(tray, attr_name=f"_{field}", state_name=field, default=0.0)
            )
    return max(timestamps)


def poll_input_wake(
    tray: IdlePowerTrayProtocol,
    *,
    loop_state: IdlePollLoopState,
    now: float,
    create_input: Callable[[], InputIdleTracker],
    read_input: Callable[[InputIdleTracker], float | None],
    create_wayland: Callable[[int], object | None],
    read_wayland: Callable[[object], bool | None],
) -> InputWakeEvidence | None:
    from keyrgb.tray.deck_pipeline import derive_deck_state
    from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_delay_s

    if not wake_on_any_input_enabled(tray):
        loop_state.input_wake.close()
        return None
    state = derive_deck_state(tray)
    if state not in (DeckState.IDLE_OFF, DeckState.CONTROLLER_SLEEP_DARK):
        loop_state.input_wake.close()
        return None
    sleep_at = _sleep_at(tray)
    if sleep_at <= 0:
        loop_state.input_wake.close()
        return None
    loop_state.input_wake.prepare((state, sleep_at))

    activity_at = 0.0
    try:
        if loop_state.input_idle_tracker is None:
            loop_state.input_idle_tracker = create_input()
        tracker = loop_state.input_idle_tracker
        if tracker is not None:
            read_input(tracker)
            activity_at = float(getattr(tracker, "last_wake_activity_at", 0.0))
    except _INPUT_ERRORS:
        logger.debug("Evdev input wake unavailable", exc_info=True)
    if activity_at <= sleep_at:
        activity_at = loop_state.input_wake.activity_at(
            epoch=(state, sleep_at), now=now, create=create_wayland, read=read_wayland
        )
    if activity_at > sleep_at:
        if read_idle_power_state_bool_field(
            tray, attr_name="_controller_sleep_off", state_name="controller_sleep_off", default=False
        ):
            # Keep host-input settling separate from firmware-wake evidence: a
            # zero poll must not claim that the pointer woke the firmware.
            if loop_state.input_wake.wake_not_before == 0.0:
                loop_state.input_wake.wake_not_before = activity_at + controller_wake_settle_delay_s(tray)
            if now < loop_state.input_wake.wake_not_before:
                return None
        return InputWakeEvidence(state, sleep_at, activity_at)
    return None


def commit_input_wake(
    tray: IdlePowerTrayProtocol,
    evidence: InputWakeEvidence,
    *,
    now: float,
    observation_revision: int | None,
) -> None:
    from keyrgb.tray.deck_pipeline import build_guards, commit_sleep_wake_intent, derive_deck_state

    def commit() -> None:
        # Re-check the epoch inside the owner: late input cannot release a newer
        # off or follow a firmware-first restore with another start.
        if derive_deck_state(tray) is not evidence.state or _sleep_at(tray) != evidence.sleep_at:
            return
        if not wake_on_any_input_enabled(tray):
            return
        commit_sleep_wake_intent(
            tray,
            SleepWakeIntent(SleepWakeIntentKind.INPUT_WAKE),
            now=now,
            guards=build_guards(tray, now=now, input_activity=evidence.activity_at > evidence.sleep_at),
        )

    run_tray_observation_if_current(tray, observation_revision, commit)
