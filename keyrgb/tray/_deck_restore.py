"""One restore transaction for manual, power, idle, and native-controller wake."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import cast

from keyrgb.core.effects.engine_support.brightness import _EngineBrightness
from keyrgb.core.lighting_result import APPLIED, BLOCKED, DEFERRED, FAILED, LightingResult, lighting_result
from keyrgb.tray._deck_state_store import _completed_lit_state, _store_deck_state
from keyrgb.tray.controllers.runtime_coordination import capture_transition_revision, run_tray_transition
from keyrgb.tray.controllers.runtime_coordinator import CoordinatorStoppedError
from keyrgb.tray.deck_state import DeckState, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import ensure_tray_idle_power_state, set_idle_power_state_field
from keyrgb.tray.protocols import IdlePowerTrayProtocol, LightingTrayProtocol

logger = logging.getLogger(__name__)


def defer_engine_fades(tray: object) -> AbstractContextManager[list[Future[bool]]]:
    engine = getattr(tray, "engine", None)
    return engine.defer_brightness_fades() if isinstance(engine, _EngineBrightness) else nullcontext([])


_ROLLBACK_FIELDS = (
    "user_forced_off",
    "power_forced_off",
    "idle_forced_off",
    "controller_sleep_off",
    "controller_sleep_off_at",
    "controller_sleep_resume_guard",
    "last_resume_at",
    "dim_temp_active",
    "dim_temp_target_brightness",
)


@dataclass
class RestoreContext:
    identity: int
    source: SleepWakeIntentKind
    origin: DeckState
    revision: int | None
    previous_fields: dict[str, object]
    was_off: bool
    completion: Future[LightingResult] = field(default_factory=Future)
    fade: Future[bool] | None = None
    reapply_requested: bool = False


def record_transition(
    tray: object,
    *,
    source: SleepWakeIntentKind,
    before: DeckState,
    after: DeckState,
    result: LightingResult,
    reason: str,
    revision: int | None = None,
) -> None:
    owner = ensure_tray_idle_power_state(tray)
    logger.log(
        logging.INFO if result.status is not DEFERRED.status else logging.DEBUG,
        "EVENT deck:transition id=%s source=%s old=%s new=%s revision=%s result=%s reason=%s "
        "owners=user:%s,power:%s,idle:%s,native:%s,dim:%s",
        owner.restore_sequence,
        source.value,
        before.value,
        after.value,
        revision if revision is not None else capture_transition_revision(tray),
        result.status.value,
        reason,
        owner.user_forced_off,
        owner.power_forced_off,
        owner.idle_forced_off,
        owner.controller_sleep_off,
        owner.dim_temp_active,
    )


def execute_restore(
    tray: IdlePowerTrayProtocol, source: SleepWakeIntentKind, leaf: Callable[[], object]
) -> LightingResult:
    from keyrgb.tray.deck_pipeline import derive_deck_state

    owner = ensure_tray_idle_power_state(tray)
    if owner.restore_context is not None:
        return LightingResult(DEFERRED.status, owner.restore_context.completion)
    origin = derive_deck_state(tray)
    owner.restore_sequence += 1
    context = RestoreContext(
        owner.restore_sequence,
        source,
        origin,
        capture_transition_revision(tray),
        {name: getattr(owner, name) for name in _ROLLBACK_FIELDS},
        bool(getattr(tray, "is_off", False)),
    )
    owner.restore_context = context
    _store_deck_state(tray, DeckState.RESTORING)
    engine = getattr(tray, "engine", None)
    prepared = False
    try:
        with defer_engine_fades(tray) as pending:
            result = lighting_result(leaf())
            if not result and isinstance(engine, _EngineBrightness):
                engine._invalidate_brightness_fade()
        prepared = True
    finally:
        if not prepared:
            # Repair state while propagating the original failure to the caller.
            finish_restore(tray, context, FAILED)
    if result and pending:
        context.fade = pending[-1]

        def completed(fade: Future[bool]) -> None:
            def accept() -> None:
                try:
                    outcome = APPLIED if fade.result() else FAILED
                except Exception:  # @quality-exception exception-transparency: async fade failures are logged and converted to an explicit failed restore result
                    logger.exception("Restore fade failed")
                    outcome = FAILED
                finish_restore(tray, context, outcome)

            try:
                run_tray_transition(tray, accept)
            except CoordinatorStoppedError:
                logger.debug("Restore completion rejected during shutdown", exc_info=True)
                if not context.completion.done():
                    context.completion.set_result(BLOCKED)

        context.fade.add_done_callback(completed)
        return LightingResult(DEFERRED.status, context.completion)
    return finish_restore(tray, context, result)


def cancel_restore(tray: IdlePowerTrayProtocol) -> None:
    """Rollback the old transaction before a newer off intent takes ownership."""
    context = ensure_tray_idle_power_state(tray).restore_context
    if context is not None:
        finish_restore(tray, context, BLOCKED)


def finish_restore(tray: IdlePowerTrayProtocol, context: RestoreContext, result: LightingResult) -> LightingResult:
    owner = ensure_tray_idle_power_state(tray)
    if owner.restore_context is not context:
        return DEFERRED
    if result and context.reapply_requested:
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        try:
            target = owner.dim_temp_target_brightness if owner.dim_temp_active else None
            result = lighting_result(start_current_effect(cast(LightingTrayProtocol, tray), brightness_override=target))
        except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError):
            logger.exception("Deferred lighting intent failed after restore")
            result = FAILED
    if result:
        _store_deck_state(tray, _completed_lit_state(tray))
    else:
        engine = getattr(tray, "engine", None)
        try:
            if isinstance(engine, _EngineBrightness):
                try:
                    engine._invalidate_brightness_fade()
                finally:
                    engine.stop()
        except Exception:  # @quality-exception exception-transparency: restore cleanup failures are logged without masking the initiating failure or stranding ownership/completion
            logger.exception("Failed to stop engine during restore rollback")
        finally:
            for name, value in context.previous_fields.items():
                set_idle_power_state_field(tray, attr_name=f"_{name}", state_name=name, value=value)
            tray.is_off = context.was_off
            _store_deck_state(tray, context.origin)
    owner.restore_context = None
    try:
        record_transition(
            tray,
            source=context.source,
            before=context.origin,
            after=owner.deck_state,
            result=result,
            reason="restore_complete" if result else ("superseded" if result.settled else "restore_failed"),
            revision=context.revision,
        )
    finally:
        context.completion.set_result(result)
    return result
