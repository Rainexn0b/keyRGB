"""Unit tests for PowerManager battery saver loop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest


class TestPowerManagerBatterySaverLoop:
    def test_classify_battery_saver_iteration_returns_classifier_plan_with_existing_runtime_inputs(self):
        from src.core.power.management import manager as manager_module
        from src.core.power.management.manager import PowerManager

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
            get_active_profile_fn=manager_module.get_active_profile,
            safe_int_attr_fn=manager_module.safe_int_attr,
        )

    def test_execute_battery_saver_iteration_plan_sleeps_and_returns_true_for_sleep_plan(self):
        from src.core.power.management import manager as manager_module
        from src.core.power.management.manager import PowerManager

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
        from src.core.power.management import manager as manager_module
        from src.core.power.management.manager import PowerManager

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
        )

    def test_run_battery_saver_iteration_delegates_classification_then_execution(self):
        from src.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())
        fake_policy = MagicMock()
        plan = object()
        coordinator = MagicMock()
        coordinator.classify.return_value = plan
        coordinator.execute.return_value = True
        pm._classify_battery_saver_iteration = coordinator.classify
        pm._execute_battery_saver_iteration_plan = coordinator.execute

        result = pm._run_battery_saver_iteration(fake_policy, poll_interval_s=2.0)

        assert result is True
        assert coordinator.mock_calls == [
            call.classify(fake_policy),
            call.execute(plan, poll_interval_s=2.0),
        ]

    def test_battery_saver_loop_covers_common_branches_and_actions(self):
        from src.core.power.management.manager import PowerManager
        from src.core.power.policies.power_source_loop_policy import (
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
                "src.core.power.management.manager.read_on_ac_power",
                side_effect=on_ac_values,
            ),
            patch(
                "src.core.power.management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "src.core.power.management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "src.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
        ):
            pm._battery_saver_loop()

        mock_kb.turn_off.assert_called_once()
        mock_kb.restore.assert_called_once()
        pm._apply_brightness_policy.assert_called_once_with(42)

    def test_battery_saver_loop_logs_and_continues_on_exception(self):
        from src.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        cfg.reload = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        def _sleep(_seconds):
            pm.monitoring = False

        with (
            patch(
                "src.core.power.management.manager.read_on_ac_power",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "src.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
            patch(
                "src.core.power.management.manager.logger.exception",
            ) as exc,
        ):
            pm._battery_saver_loop()

        exc.assert_called_once()

    def test_battery_saver_loop_propagates_unexpected_exceptions(self):
        from src.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        cfg.reload = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        with patch(
            "src.core.power.management.manager.read_on_ac_power",
            side_effect=AssertionError("unexpected battery loop bug"),
        ):
            with pytest.raises(AssertionError, match="unexpected battery loop bug"):
                pm._battery_saver_loop()

    def test_battery_saver_loop_ignores_ac_battery_overrides_for_dim_profile(self):
        from src.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.is_off = False

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.brightness = 10
        cfg.management_enabled = True

        # Values that would normally be applied.
        cfg.ac_lighting_enabled = False
        cfg.battery_lighting_enabled = False
        cfg.ac_lighting_brightness = 25
        cfg.battery_lighting_brightness = 5

        cfg.battery_saver_enabled = False
        cfg.battery_saver_brightness = 25

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        fake_policy = MagicMock()
        fake_policy.update.return_value = SimpleNamespace(skip=True, actions=[])

        sleep_calls = {"n": 0}

        def _sleep(_seconds):
            sleep_calls["n"] += 1
            pm.monitoring = False

        with (
            patch(
                "src.core.power.management.manager.read_on_ac_power",
                return_value=True,
            ),
            patch(
                "src.core.power.management.manager.get_active_profile",
                return_value="dim",
            ),
            patch(
                "src.core.power.management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "src.core.power.management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "src.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
        ):
            pm._battery_saver_loop()

        # The policy should see neutralized overrides.
        (inputs,), _kwargs = fake_policy.update.call_args
        assert inputs.ac_enabled is True
        assert inputs.battery_enabled is True
        assert inputs.ac_brightness_override is None
        assert inputs.battery_brightness_override is None

    def test_battery_saver_loop_respects_ac_battery_overrides_for_light_profile(self):
        from src.core.power.management.manager import PowerManager

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
                "src.core.power.management.manager.read_on_ac_power",
                return_value=True,
            ),
            patch(
                "src.core.power.management.manager.get_active_profile",
                return_value="light",
            ),
            patch(
                "src.core.power.management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "src.core.power.management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "src.core.power.management.manager.time.sleep",
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
