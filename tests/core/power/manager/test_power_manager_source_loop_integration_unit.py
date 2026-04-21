"""Integration seam tests for apply_power_source_actions and the
full input→policy→action pipeline in _manager_helpers.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# apply_power_source_actions — single-action dispatch
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_turn_off_calls_kb_turn_off() -> None:
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import TurnOffKeyboard

    kb = MagicMock()
    apply_power_source_actions(
        kb_controller=kb,
        actions=(TurnOffKeyboard(),),
        apply_brightness=MagicMock(),
    )

    kb.turn_off.assert_called_once_with()
    kb.restore.assert_not_called()


def test_apply_power_source_actions_restore_calls_kb_restore() -> None:
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import RestoreKeyboard

    kb = MagicMock()
    apply_power_source_actions(
        kb_controller=kb,
        actions=(RestoreKeyboard(),),
        apply_brightness=MagicMock(),
    )

    kb.restore.assert_called_once_with()
    kb.turn_off.assert_not_called()


def test_apply_power_source_actions_apply_brightness_calls_callback_with_value() -> None:
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import ApplyBrightness

    apply_brightness = MagicMock()
    apply_power_source_actions(
        kb_controller=MagicMock(),
        actions=(ApplyBrightness(42),),
        apply_brightness=apply_brightness,
    )

    apply_brightness.assert_called_once_with(42)


# ---------------------------------------------------------------------------
# apply_power_source_actions — mixed action list
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_mixed_list_triggers_all_side_effects_in_sequence() -> None:
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import (
        ApplyBrightness,
        RestoreKeyboard,
        TurnOffKeyboard,
    )

    call_order: list[str] = []

    class _OrderedController:
        def turn_off(self) -> None:
            call_order.append("turn_off")

        def restore(self) -> None:
            call_order.append("restore")

    def _track_brightness(value: int) -> None:
        call_order.append(f"brightness:{value}")

    apply_power_source_actions(
        kb_controller=_OrderedController(),
        actions=(TurnOffKeyboard(), RestoreKeyboard(), ApplyBrightness(30)),
        apply_brightness=_track_brightness,
    )

    assert call_order == ["turn_off", "restore", "brightness:30"]


# ---------------------------------------------------------------------------
# apply_power_source_actions — resilience: swallowed RuntimeError
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_controller_runtime_error_is_swallowed_and_loop_continues() -> None:
    """A RuntimeError from a controller action must be caught; subsequent actions still run."""
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import ApplyBrightness, TurnOffKeyboard

    class _FailingController:
        def turn_off(self) -> None:
            raise RuntimeError("backend unavailable")

    apply_brightness = MagicMock()

    with patch("src.core.power.management._manager_helpers.logger.exception") as mock_exc:
        apply_power_source_actions(
            kb_controller=_FailingController(),
            actions=(TurnOffKeyboard(), ApplyBrightness(15)),
            apply_brightness=apply_brightness,
        )

    # Exception must have been logged, not re-raised.
    mock_exc.assert_called_once()
    assert mock_exc.call_args.args[1] == "turn_off"

    # The ApplyBrightness action after the failure must still be dispatched.
    apply_brightness.assert_called_once_with(15)


# ---------------------------------------------------------------------------
# End-to-end pipeline seam: build_power_source_loop_inputs →
# PowerSourceLoopPolicy.update() → apply_power_source_actions
# ---------------------------------------------------------------------------


class _FakeConfig:
    power_management_enabled = True
    management_enabled = True
    brightness = 50
    ac_lighting_enabled = True
    battery_lighting_enabled = True
    ac_lighting_brightness = None
    battery_lighting_brightness = None
    battery_saver_enabled = False
    battery_saver_brightness = 25

    def reload(self) -> None:
        pass


def test_pipeline_on_ac_enabled_no_overrides_does_not_turn_off_keyboard() -> None:
    """Full pipeline: AC plugged in, lighting enabled, no overrides.

    The policy must not emit a TurnOffKeyboard action on the first tick when
    the keyboard is already on and ac_enabled=True.
    """
    from src.core.power.management._manager_helpers import (
        apply_power_source_actions,
        build_power_source_loop_inputs,
    )
    from src.core.power.policies.power_source_loop_policy import PowerSourceLoopPolicy

    _values = {"brightness": 50, "battery_saver_brightness": 25}

    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _FakeConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_active_profile_fn=lambda: "light",
        safe_int_attr_fn=lambda obj, name, default=0: _values.get(name, default),
    )

    assert inputs is not None, "pipeline should not be disabled for this config"

    policy = PowerSourceLoopPolicy()
    result = policy.update(inputs)

    apply_brightness = MagicMock()
    apply_power_source_actions(
        kb_controller=kb,
        actions=result.actions,
        apply_brightness=apply_brightness,
    )

    kb.turn_off.assert_not_called()
