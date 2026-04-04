from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_build_power_source_loop_inputs_preserves_overrides_when_profile_lookup_raises() -> None:
    from src.core.power.management._manager_helpers import build_power_source_loop_inputs

    class _Config:
        power_management_enabled = True
        brightness = 35
        ac_lighting_enabled = False
        battery_lighting_enabled = True
        ac_lighting_brightness = 45
        battery_lighting_brightness = 15
        battery_saver_enabled = True
        battery_saver_brightness = 20

        def reload(self) -> None:
            return None

    values = {
        "brightness": 35,
        "battery_saver_brightness": 20,
    }

    inputs = build_power_source_loop_inputs(
        _Config(),
        kb_controller=MagicMock(is_off=False),
        on_ac=True,
        now_mono=123.0,
        get_active_profile_fn=MagicMock(side_effect=RuntimeError("profile failed")),
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None
    assert inputs.ac_enabled is False
    assert inputs.battery_enabled is True
    assert inputs.ac_brightness_override == 45
    assert inputs.battery_brightness_override == 15


def test_apply_power_source_actions_logs_controller_failures_and_keeps_processing() -> None:
    from src.core.power.management._manager_helpers import apply_power_source_actions
    from src.core.power.policies.power_source_loop_policy import ApplyBrightness, RestoreKeyboard, TurnOffKeyboard

    class _Controller:
        def turn_off(self) -> None:
            raise RuntimeError("turn off failed")

        def restore(self) -> None:
            raise RuntimeError("restore failed")

    apply_brightness = MagicMock()

    with patch("src.core.power.management._manager_helpers.logger.exception") as exc:
        apply_power_source_actions(
            kb_controller=_Controller(),
            actions=(TurnOffKeyboard(), RestoreKeyboard(), ApplyBrightness(25)),
            apply_brightness=apply_brightness,
        )

    apply_brightness.assert_called_once_with(25)
    assert exc.call_count == 2
    assert exc.call_args_list[0].args == ("Power-source controller action %s failed", "turn_off")
    assert exc.call_args_list[1].args == ("Power-source controller action %s failed", "restore")


def test_is_intentionally_off_requires_literal_true_for_controller_flags() -> None:
    from src.core.power.management._manager_helpers import is_intentionally_off

    class _Controller:
        user_forced_off = 1
        _user_forced_off = "yes"

    assert (
        is_intentionally_off(
            kb_controller=_Controller(),
            config=object(),
            safe_int_attr_fn=lambda obj, name, default=0: 25,
        )
        is False
    )


def test_is_intentionally_off_returns_false_when_safe_int_reader_raises() -> None:
    from src.core.power.management._manager_helpers import is_intentionally_off

    class _Controller:
        @property
        def user_forced_off(self):
            raise RuntimeError("flag failed")

        @property
        def _user_forced_off(self):
            raise RuntimeError("private flag failed")

    assert (
        is_intentionally_off(
            kb_controller=_Controller(),
            config=object(),
            safe_int_attr_fn=lambda obj, name, default=0: (_ for _ in ()).throw(RuntimeError("brightness failed")),
        )
        is False
    )
