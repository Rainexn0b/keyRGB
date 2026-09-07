"""Unit tests for PowerManager battery saver loop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestPowerManagerBatterySaverLoop:
    def test_stabilize_on_ac_state_requires_two_consecutive_changed_samples(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())

        assert pm._stabilize_on_ac_state(True) is True
        assert pm._stabilize_on_ac_state(False) is True
        assert pm._stabilize_on_ac_state(False) is False
        assert pm._stabilize_on_ac_state(True) is False
        assert pm._stabilize_on_ac_state(True) is True

    def test_stabilize_on_ac_state_reuses_last_stable_value_when_read_is_unavailable(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())

        assert pm._stabilize_on_ac_state(True) is True
        assert pm._stabilize_on_ac_state(None) is True
        assert pm._stabilize_on_ac_state(False) is True
        assert pm._stabilize_on_ac_state(False) is False

    def test_classify_battery_saver_iteration_returns_classifier_plan_with_existing_runtime_inputs(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        plan = SimpleNamespace(should_sleep=False, actions=("action",))
        fake_policy = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)

        with (
            patch.object(manager_module, "read_on_ac_power", return_value=True),
            patch.object(manager_module.time, "monotonic", return_value=123.0),
            patch.object(manager_module, "build_power_source_loop_inputs", return_value="loop-inputs") as build_inputs,
            patch.object(manager_module, "classify_power_source_iteration", return_value=plan) as classify,
        ):
            result = pm._classify_battery_saver_iteration(fake_policy)
            build_loop_inputs_fn = classify.call_args.kwargs["build_loop_inputs_fn"]
            loop_inputs = build_loop_inputs_fn(False)

        assert result is plan
        assert loop_inputs == "loop-inputs"
        assert classify.call_args.kwargs["raw_on_ac"] is True
        assert classify.call_args.kwargs["policy"] is fake_policy
        build_inputs.assert_called_once_with(
            cfg,
            mock_kb,
            on_ac=False,
            now_mono=123.0,
            get_power_mode_status_fn=manager_module.get_system_power_status,
            get_active_perkey_profile_fn=manager_module.get_active_perkey_profile,
            safe_int_attr_fn=manager_module.safe_int_attr,
        )

    def test_execute_battery_saver_iteration_plan_sleeps_and_returns_true_for_sleep_plan(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())
        plan = SimpleNamespace(should_sleep=True, actions=("ignored",))

        with (
            patch.object(manager_module.time, "sleep") as sleep,
            patch.object(manager_module, "apply_power_source_actions") as apply_actions,
        ):
            result = pm._execute_battery_saver_iteration_plan(plan, poll_interval_s=2.0)

        assert result is True
        sleep.assert_called_once_with(2.0)
        apply_actions.assert_not_called()

    def test_execute_battery_saver_iteration_plan_applies_actions_and_returns_false(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb, config=MagicMock())
        pm._apply_brightness_policy = MagicMock()
        plan = SimpleNamespace(should_sleep=False, actions=("action-1", "action-2"))

        with (
            patch.object(manager_module.time, "sleep") as sleep,
            patch.object(manager_module, "apply_power_source_actions") as apply_actions,
        ):
            result = pm._execute_battery_saver_iteration_plan(plan, poll_interval_s=2.0)

        assert result is False
        sleep.assert_not_called()
        apply_actions.assert_called_once_with(
            kb_controller=mock_kb,
            actions=plan.actions,
            apply_brightness=pm._apply_brightness_policy,
            activate_power_mode=pm._activate_power_source_mode,
            activate_perkey_profile=pm._activate_power_source_perkey_profile,
        )

    def test_execute_battery_saver_iteration_plan_wires_power_mode_apply_feedback(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.policies.power_source_loop_policy import ActivatePowerMode
        from keyrgb.core.power.system import PowerMode

        pm = PowerManager(MagicMock(), config=MagicMock())
        policy = MagicMock()
        plan = SimpleNamespace(should_sleep=False, actions=(ActivatePowerMode(PowerMode.PERFORMANCE),))

        with patch.object(manager_module, "apply_power_source_actions") as apply_actions:
            assert (
                pm._execute_battery_saver_iteration_plan(
                    plan,
                    poll_interval_s=2.0,
                    record_power_mode_apply_result_fn=policy.record_power_mode_apply_result,
                )
                is False
            )

        assert apply_actions.call_args.kwargs["record_power_mode_apply_result"] is policy.record_power_mode_apply_result

    def test_activate_power_source_mode_uses_noninteractive_auth(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.system import PowerMode

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb, config=MagicMock())

        with patch.object(manager_module, "set_system_power_mode", return_value=True) as set_mode:
            pm._activate_power_source_mode(PowerMode.EXTREME_SAVER)

        set_mode.assert_called_once_with(PowerMode.EXTREME_SAVER, allow_interactive=False)
        mock_kb._refresh_system_power_view.assert_called_once_with()
        # The manager never rebuilds the menu directly; the tray delegate
        # defers one coalesced rebuild until after the transition completes.
        mock_kb._update_menu.assert_not_called()

    def test_activate_power_source_mode_skips_view_refresh_when_apply_fails(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.system import PowerMode

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb, config=MagicMock())

        with patch.object(manager_module, "set_system_power_mode", return_value=False):
            pm._activate_power_source_mode(PowerMode.EXTREME_SAVER)

        mock_kb._refresh_system_power_view.assert_not_called()
        mock_kb._update_menu.assert_not_called()

    def test_activate_power_source_mode_tolerates_tray_without_view_refresh(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.system import PowerMode

        pm = PowerManager(SimpleNamespace(), config=MagicMock())

        with patch.object(manager_module, "set_system_power_mode", return_value=True):
            pm._activate_power_source_mode(PowerMode.PERFORMANCE)

    def test_activate_power_source_mode_contains_view_refresh_errors(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.system import PowerMode

        mock_kb = MagicMock()
        mock_kb._refresh_system_power_view.side_effect = RuntimeError("view boom")
        pm = PowerManager(mock_kb, config=MagicMock())

        with patch.object(manager_module, "set_system_power_mode", return_value=True):
            pm._activate_power_source_mode(PowerMode.EXTREME_SAVER)

        mock_kb._refresh_system_power_view.assert_called_once_with()

    def test_activate_power_source_mode_logs_observation_mismatch_without_failing_apply(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.system import PowerMode

        mock_kb = MagicMock()
        mock_kb._refresh_system_power_view.return_value = SimpleNamespace(
            supported=True,
            mode=PowerMode.BALANCED,
        )
        pm = PowerManager(mock_kb, config=MagicMock())

        with (
            patch.object(manager_module, "set_system_power_mode", return_value=True),
            patch.object(manager_module.logger, "debug") as debug,
        ):
            assert pm._activate_power_source_mode(PowerMode.PERFORMANCE) is True

        debug.assert_called_once_with(
            "Power-source mode apply succeeded but observation reports %s (desired %s)",
            PowerMode.BALANCED.value,
            PowerMode.PERFORMANCE.value,
        )

    def test_battery_saver_loop_covers_common_branches_and_actions(self):
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.policies.power_source_loop_policy import (
            ApplyBrightness,
            RestoreKeyboard,
            TurnOffKeyboard,
        )

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        mock_kb.restore = MagicMock()
        mock_kb.is_off = False

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.brightness = "not-an-int"
        cfg.management_enabled = True
        cfg.ac_lighting_enabled = True
        cfg.battery_lighting_enabled = True
        cfg.ac_lighting_brightness = None
        cfg.battery_lighting_brightness = None
        cfg.battery_saver_enabled = True
        cfg.battery_saver_brightness = 25

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True
        pm._apply_brightness_policy = MagicMock()

        result_skip = SimpleNamespace(skip=True, actions=[])
        result_actions = SimpleNamespace(
            skip=False,
            actions=[
                TurnOffKeyboard(),
                RestoreKeyboard(),
                ApplyBrightness(brightness=42),
            ],
        )
        fake_policy = MagicMock()
        fake_policy.update.side_effect = [result_skip, result_actions]

        on_ac_values = [None, True, True, True]

        sleep_calls = {"n": 0}

        def _sleep(_seconds):
            sleep_calls["n"] += 1
            if sleep_calls["n"] == 1:
                return
            if sleep_calls["n"] == 2:
                cfg.management_enabled = False
                return
            if sleep_calls["n"] == 3:
                cfg.management_enabled = True
                return
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.read_on_ac_power",
                side_effect=on_ac_values,
            ),
            patch(
                "keyrgb.core.power.management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "keyrgb.core.power.management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "keyrgb.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
        ):
            pm._battery_saver_loop()

        mock_kb.turn_off.assert_called_once()
        mock_kb.restore.assert_called_once()
        pm._apply_brightness_policy.assert_called_once_with(42)

    def test_battery_saver_loop_respects_ac_battery_overrides_for_light_profile(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.is_off = False

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.brightness = 10
        cfg.management_enabled = True

        cfg.ac_lighting_enabled = False
        cfg.battery_lighting_enabled = True
        cfg.ac_lighting_brightness = 25
        cfg.battery_lighting_brightness = 5

        cfg.battery_saver_enabled = False
        cfg.battery_saver_brightness = 25

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        fake_policy = MagicMock()
        fake_policy.update.return_value = SimpleNamespace(skip=True, actions=[])

        def _sleep(_seconds):
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.read_on_ac_power",
                return_value=True,
            ),
            patch(
                "keyrgb.core.power.management.manager.get_system_power_status",
                return_value=SimpleNamespace(supported=True, mode=None),
            ),
            patch(
                "keyrgb.core.power.management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "keyrgb.core.power.management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "keyrgb.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
        ):
            pm._battery_saver_loop()

        # The policy should see config values unchanged.
        (inputs,), _kwargs = fake_policy.update.call_args
        assert inputs.ac_enabled is False
        assert inputs.battery_enabled is True
        assert inputs.ac_brightness_override == 25
        assert inputs.battery_brightness_override == 5

    def test_activate_power_source_perkey_profile_skips_missing_profile(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())

        with (
            patch.object(manager_module, "list_perkey_profiles", return_value=["default", "gaming"]),
            patch.object(manager_module, "activate_perkey_profile") as activate_profile,
            patch.object(manager_module.logger, "warning") as warning,
        ):
            pm._activate_power_source_perkey_profile("battery")

        activate_profile.assert_not_called()
        warning.assert_called_once_with("Skipping missing power-source lighting profile '%s'", "battery")

    def test_activate_power_source_perkey_profile_uses_tray_transition_when_available(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.config = SimpleNamespace(brightness=25, effect="perkey", per_key_colors={(0, 0): (1, 2, 3)})
        mock_kb._power_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(power_forced_off=False)
        mock_kb._apply_power_source_perkey_profile_transition = MagicMock(return_value=True)

        pm = PowerManager(mock_kb, config=MagicMock())

        with (
            patch.object(manager_module, "list_perkey_profiles", return_value=["battery"]),
            patch.object(manager_module.perkey_profiles, "set_active_profile", return_value="battery") as set_active,
            patch.object(
                manager_module.perkey_profiles,
                "load_per_key_colors",
                return_value={(0, 0): (9, 9, 9)},
            ) as load_colors,
            patch.object(manager_module.perkey_profiles, "apply_profile_to_config") as apply_profile,
            patch.object(manager_module.time, "monotonic", return_value=123.0),
        ):
            pm._activate_power_source_perkey_profile("battery")

        set_active.assert_called_once_with("battery")
        load_colors.assert_called_once_with("battery")
        apply_profile.assert_called_once_with(mock_kb.config, {(0, 0): (9, 9, 9)})
        mock_kb._apply_power_source_perkey_profile_transition.assert_called_once_with()
        mock_kb._start_current_effect.assert_not_called()
        assert mock_kb._last_power_source_transition_at == 123.0
        assert mock_kb._last_power_source_transition_profile_name == "battery"
        mock_kb._update_icon.assert_called_once()
        mock_kb._update_menu.assert_not_called()

    def test_activate_power_source_perkey_profile_restarts_when_tray_transition_declines(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.config = SimpleNamespace(brightness=25, effect="reactive_ripple", per_key_colors={(0, 0): (1, 2, 3)})
        mock_kb._power_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(power_forced_off=False)
        mock_kb._apply_power_source_perkey_profile_transition = MagicMock(return_value=False)

        pm = PowerManager(mock_kb, config=MagicMock())

        with (
            patch.object(manager_module, "list_perkey_profiles", return_value=["battery"]),
            patch.object(manager_module.perkey_profiles, "set_active_profile", return_value="battery"),
            patch.object(manager_module.perkey_profiles, "load_per_key_colors", return_value={(0, 0): (9, 9, 9)}),
            patch.object(manager_module.perkey_profiles, "apply_profile_to_config"),
            patch.object(manager_module.time, "monotonic", return_value=123.0),
        ):
            pm._activate_power_source_perkey_profile("battery")

        mock_kb._apply_power_source_perkey_profile_transition.assert_called_once_with()
        mock_kb._start_current_effect.assert_called_once_with()
        assert mock_kb._last_power_source_transition_at == 123.0
        assert mock_kb._last_power_source_transition_profile_name == "battery"
        mock_kb._update_icon.assert_called_once()
        mock_kb._update_menu.assert_not_called()
