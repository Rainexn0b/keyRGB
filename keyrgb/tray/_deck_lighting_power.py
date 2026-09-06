"""Lighting-power intent commit for the deck pipeline."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from keyrgb.tray._deck_state_store import _completed_lit_state, _store_deck_state
from keyrgb.tray.deck_state import DeckState, SleepWakeGuards, SleepWakeIntent, SleepWakeIntentKind, next_state
from keyrgb.tray.idle_power_state import is_dim_temp_active

if TYPE_CHECKING:
    from keyrgb.tray.protocols import IdlePowerTrayProtocol

logger = logging.getLogger("keyrgb.tray.deck_pipeline")


def commit_lighting_power_intent(
    tray: IdlePowerTrayProtocol,
    intent_kind: SleepWakeIntentKind,
    leaf_fn: Callable[[], object],
    *,
    now: float | None = None,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
    fade_in_duration_s: float | None = None,
) -> bool:
    """Pipeline decision for menu/power ``is_off`` writes.

    The four ``lighting_controller`` entrypoints (``turn_on``, ``turn_off``,
    ``power_turn_off``, ``power_restore``) must be decided by
    ``DeckPipeline`` using ``MANUAL_ON``/``MANUAL_OFF``/``POWER_OFF``/
    ``POWER_RESUME`` before their existing device-writing leaves run.  This
    helper owns that decision plus the ``RESTORING`` firewall:

    * bare ``tray.is_off=True`` with no forced-off flag is treated as
      ``POWER_OFF`` only for ``MANUAL_ON``/``POWER_RESUME`` via the narrow
      override (``hardware_apply_deferred`` stays false);
    * a restoring leaf publishes ``RESTORING`` before it blocks on its fade,
      then ``LIT``/``DIM_TEMP`` on success or the origin on failure;
    * a second wake intent while ``RESTORING`` coalesces via
      ``next_state(RESTORING, wake) -> noop``.
    """

    from keyrgb.tray.deck_pipeline import (
        build_guards,
        decide_sleep_wake,
        derive_deck_state,
        respect_enabled,
    )

    origin = derive_deck_state(tray)
    now_val = float(now if now is not None else time.monotonic())
    respect_val = respect_enabled(tray) if respect is None else bool(respect)
    guards_val = guards if guards is not None else build_guards(tray, now=now_val)
    plan = decide_sleep_wake(
        tray,
        SleepWakeIntent(intent_kind),
        now=now_val,
        respect=respect_val,
        guards=guards_val,
    )
    if plan.deferred:
        return False
    if not plan.should_commit:
        # Power restore must still run its housekeeping (last_resume_at, guard
        # clear) even when the pipeline correctly blocks the restore while
        # USER_OFF/IDLE_OFF remains authoritative.
        if intent_kind is SleepWakeIntentKind.POWER_RESUME and origin in (
            DeckState.USER_OFF,
            DeckState.IDLE_OFF,
        ):
            leaf_fn()
        return False

    if plan.state is DeckState.RESTORING:
        _store_deck_state(tray, DeckState.RESTORING)
        seeded = _seed_lighting_power_restore_windows(
            tray,
            fade_in_duration_s=fade_in_duration_s,
        )
        leaf_completed = False
        try:
            leaf_result = leaf_fn()
            leaf_completed = True
        finally:
            if seeded:
                _consume_lighting_power_restore_seed(tray)
            if not leaf_completed:
                # Preserve the caller-visible exception while repairing the
                # pipeline state so later intents are not stranded RESTORING.
                _store_deck_state(tray, origin)

        success = leaf_result is not False
        if intent_kind in (SleepWakeIntentKind.MANUAL_ON, SleepWakeIntentKind.POWER_RESUME):
            try:
                if bool(getattr(tray, "is_off", False)):
                    success = False
            except (AttributeError, TypeError, ValueError):
                pass

        if success:
            dim_active = is_dim_temp_active(tray)
            guards2 = SleepWakeGuards(dim_temp_still_active=bool(dim_active))
            plan2 = next_state(
                DeckState.RESTORING,
                SleepWakeIntent(SleepWakeIntentKind.RESTORE_COMPLETE),
                respect=respect_val,
                guards=guards2,
            )
            if plan2.should_commit:
                _store_deck_state(tray, plan2.state)
            else:
                _store_deck_state(tray, _completed_lit_state(tray))
            return True

        guards2 = SleepWakeGuards(dim_temp_still_active=is_dim_temp_active(tray))
        plan2 = next_state(
            DeckState.RESTORING,
            SleepWakeIntent(SleepWakeIntentKind.RESTORE_FAILED, restore_origin=origin),
            respect=respect_val,
            guards=guards2,
        )
        if plan2.should_commit:
            _store_deck_state(tray, plan2.state)
        else:
            _store_deck_state(tray, origin)
        return False

    leaf_fn()
    _store_deck_state(tray, plan.state)
    return True


def _seed_lighting_power_restore_windows(
    tray: IdlePowerTrayProtocol,
    *,
    fade_in_duration_s: float | None,
) -> bool:
    """Enter the shared one-seed contract for manual/power reactive restores."""

    from keyrgb.core.effects.catalog import REACTIVE_EFFECTS
    from keyrgb.core.effects.reactive._reactive_restore_seed import seed_reactive_restore_windows
    from keyrgb.core.utils.safe_attrs import safe_str_attr
    from keyrgb.tray.controllers._power._transition_constants import idle_fade_duration_s

    effect = safe_str_attr(getattr(tray, "config", None), "effect", default="none") or "none"
    if effect not in REACTIVE_EFFECTS:
        return False
    duration = idle_fade_duration_s(tray.config) if fade_in_duration_s is None else max(0.0, float(fade_in_duration_s))
    try:
        return bool(
            seed_reactive_restore_windows(
                tray.engine,
                fade_in_duration_s=float(duration),
            )
        )
    except (AttributeError, TypeError, ValueError):
        logger.warning("Reactive lighting-power restore seed failed", exc_info=True)
        return False


def _consume_lighting_power_restore_seed(tray: IdlePowerTrayProtocol) -> None:
    """Consume only the original seed when a restart did not consume it."""

    from keyrgb.core.effects.reactive._reactive_restore_seed import apply_queued_reactive_restore_seed

    try:
        apply_queued_reactive_restore_seed(tray.engine)
    except (AttributeError, TypeError, ValueError):
        logger.warning("Reactive lighting-power restore seed cleanup failed", exc_info=True)
