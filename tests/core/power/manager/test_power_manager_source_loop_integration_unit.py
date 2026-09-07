"""Unit tests for apply_power_source_actions dispatch in _manager_helpers.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from keyrgb.core.power.system import PowerMode

# ---------------------------------------------------------------------------
# apply_power_source_actions — single-action dispatch
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_turn_off_calls_kb_turn_off() -> None:
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import TurnOffKeyboard

    kb = MagicMock()
    apply_power_source_actions(
        kb_controller=kb,
        actions=(TurnOffKeyboard(),),
        apply_brightness=MagicMock(),
        activate_power_mode=MagicMock(),
        activate_perkey_profile=MagicMock(),
    )

    kb.turn_off.assert_called_once_with()
    kb.restore.assert_not_called()


def test_apply_power_source_actions_restore_calls_kb_restore() -> None:
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import RestoreKeyboard

    kb = MagicMock()
    apply_power_source_actions(
        kb_controller=kb,
        actions=(RestoreKeyboard(),),
        apply_brightness=MagicMock(),
        activate_power_mode=MagicMock(),
        activate_perkey_profile=MagicMock(),
    )

    kb.restore.assert_called_once_with()
    kb.turn_off.assert_not_called()


def test_apply_power_source_actions_apply_brightness_calls_callback_with_value() -> None:
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import ApplyBrightness

    apply_brightness = MagicMock()
    apply_power_source_actions(
        kb_controller=MagicMock(),
        actions=(ApplyBrightness(42),),
        apply_brightness=apply_brightness,
        activate_power_mode=MagicMock(),
        activate_perkey_profile=MagicMock(),
    )

    apply_brightness.assert_called_once_with(42)


def test_apply_power_source_actions_activate_power_mode_calls_callback() -> None:
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import ActivatePowerMode

    activate_power_mode = MagicMock()
    apply_power_source_actions(
        kb_controller=MagicMock(),
        actions=(ActivatePowerMode(PowerMode.PERFORMANCE),),
        apply_brightness=MagicMock(),
        activate_power_mode=activate_power_mode,
        activate_perkey_profile=MagicMock(),
    )

    activate_power_mode.assert_called_once_with(PowerMode.PERFORMANCE)


# ---------------------------------------------------------------------------
# apply_power_source_actions — mixed action list
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_mixed_list_triggers_all_side_effects_in_sequence() -> None:
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import (
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
        activate_power_mode=lambda mode: call_order.append(f"power_mode:{mode.value}"),
        activate_perkey_profile=lambda profile_name: call_order.append(f"profile:{profile_name}"),
    )

    assert call_order == ["turn_off", "restore", "brightness:30"]


# ---------------------------------------------------------------------------
# apply_power_source_actions — resilience: swallowed RuntimeError
# ---------------------------------------------------------------------------


def test_apply_power_source_actions_controller_runtime_error_is_swallowed_and_loop_continues() -> None:
    """A RuntimeError from a controller action must be caught; subsequent actions still run."""
    from keyrgb.core.power.management._manager_helpers import apply_power_source_actions
    from keyrgb.core.power.policies.power_source_loop_policy import ApplyBrightness, TurnOffKeyboard

    class _FailingController:
        def turn_off(self) -> None:
            raise RuntimeError("backend unavailable")

    apply_brightness = MagicMock()

    with patch("keyrgb.core.power.management._manager_helpers.logger.exception") as mock_exc:
        apply_power_source_actions(
            kb_controller=_FailingController(),
            actions=(TurnOffKeyboard(), ApplyBrightness(15)),
            apply_brightness=apply_brightness,
            activate_power_mode=MagicMock(),
            activate_perkey_profile=MagicMock(),
        )

    # Exception must have been logged, not re-raised.
    mock_exc.assert_called_once()
    assert mock_exc.call_args.args[1] == "turn_off"

    # The ApplyBrightness action after the failure must still be dispatched.
    apply_brightness.assert_called_once_with(15)
