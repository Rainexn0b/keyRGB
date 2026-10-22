"""A secondary cleanup failure must not orphan a restore transaction."""

from __future__ import annotations

from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from keyrgb.core.effects.engine_support.brightness import _EngineBrightness
from keyrgb.core.lighting_result import APPLIED, BLOCKED, FAILED
from keyrgb.tray._deck_restore import cancel_restore, execute_restore, finish_restore
from keyrgb.tray.deck_state import DeckState, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import TrayIdlePowerState


class CleanupEngine(_EngineBrightness):
    def __init__(self, cleanup_error):
        self.kb_lock = RLock()
        self._brightness_fade_lock = RLock()
        self._brightness_fade_token = 0
        self.stop = Mock(side_effect=cleanup_error)


@pytest.mark.parametrize("cleanup_error", [RuntimeError("join failed"), AssertionError("cleanup bug")])
@pytest.mark.parametrize("leaf_raises", [False, True])
def test_failed_restore_settles_and_preserves_original_error(cleanup_error, leaf_raises, caplog):
    owner = TrayIdlePowerState(power_forced_off=True, dim_temp_active=True, dim_temp_target_brightness=10)
    engine = CleanupEngine(cleanup_error)
    tray = SimpleNamespace(engine=engine, tray_idle_power_state=owner, is_off=True)
    contexts = []
    original_error = OSError("restore device failure")

    def leaf():
        contexts.append(owner.restore_context)
        owner.power_forced_off = False
        owner.dim_temp_active = False
        owner.dim_temp_target_brightness = None
        tray.is_off = False
        if leaf_raises:
            raise original_error
        return False

    if leaf_raises:
        with pytest.raises(OSError) as raised:
            execute_restore(tray, SleepWakeIntentKind.POWER_RESUME, leaf)
        assert raised.value is original_error
    else:
        assert execute_restore(tray, SleepWakeIntentKind.POWER_RESUME, leaf) is FAILED
    context = contexts[0]
    assert context.completion.result(timeout=0) is FAILED
    assert owner.restore_context is None
    assert owner.deck_state is DeckState.POWER_OFF
    assert owner.power_forced_off and tray.is_off
    assert owner.dim_temp_active and owner.dim_temp_target_brightness == 10
    engine.stop.assert_called_once()
    assert any(record.exc_info and record.exc_info[1] is cleanup_error for record in caplog.records)
    # A duplicate completion cannot overwrite the failed result or roll back again.
    finish_restore(tray, context, APPLIED)
    assert context.completion.result(timeout=0) is FAILED
    engine.stop.assert_called_once()


def test_cancellation_clears_restore_even_when_engine_stop_fails():
    owner = TrayIdlePowerState(power_forced_off=True)
    tray = SimpleNamespace(engine=CleanupEngine(RuntimeError("join failed")), tray_idle_power_state=owner, is_off=True)
    contexts = []

    def leaf():
        contexts.append(owner.restore_context)
        owner.power_forced_off = False
        tray.is_off = False
        cancel_restore(tray)
        return True

    execute_restore(tray, SleepWakeIntentKind.POWER_RESUME, leaf)
    assert contexts[0].completion.result(timeout=0) is BLOCKED
    assert owner.restore_context is None
    assert owner.deck_state is DeckState.POWER_OFF
    assert tray.is_off
