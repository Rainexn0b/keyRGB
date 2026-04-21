from __future__ import annotations

from unittest.mock import MagicMock

from src.core.power.management._manager_brightness_execution import (
    classify_brightness_execution,
    execute_brightness_execution,
)


def test_classify_and_execute_brightness_prefers_controller_hook() -> None:
    kb_controller = MagicMock()
    kb_controller.apply_brightness_from_power_policy = MagicMock()
    kb_controller.engine = MagicMock()

    plan = classify_brightness_execution(kb_controller=kb_controller, brightness=42)

    assert plan.should_execute is True
    assert plan.controller_apply_fn is kb_controller.apply_brightness_from_power_policy
    assert plan.engine is None

    sync_config = MagicMock()
    execute_brightness_execution(
        plan=plan,
        sync_config_brightness_fn=sync_config,
    )

    kb_controller.apply_brightness_from_power_policy.assert_called_once_with(42)
    sync_config.assert_not_called()
    kb_controller.engine.set_brightness.assert_not_called()


def test_execute_brightness_engine_fallback_syncs_config_before_engine() -> None:
    kb_controller = MagicMock()
    del kb_controller.apply_brightness_from_power_policy

    call_order: list[tuple[str, int]] = []
    engine = MagicMock()
    engine.set_brightness.side_effect = lambda brightness: call_order.append(("engine", brightness))
    kb_controller.engine = engine

    plan = classify_brightness_execution(kb_controller=kb_controller, brightness=75)

    assert plan.should_execute is True
    assert plan.controller_apply_fn is None
    assert plan.engine is engine

    def _sync_config(brightness: int) -> None:
        call_order.append(("sync", brightness))

    execute_brightness_execution(
        plan=plan,
        sync_config_brightness_fn=_sync_config,
    )

    assert call_order == [("sync", 75), ("engine", 75)]


def test_classify_and_execute_brightness_noop_without_hook_or_engine() -> None:
    kb_controller = MagicMock(spec=[])

    plan = classify_brightness_execution(kb_controller=kb_controller, brightness=10)

    assert plan.should_execute is False
    assert plan.controller_apply_fn is None
    assert plan.engine is None

    sync_config = MagicMock()
    execute_brightness_execution(
        plan=plan,
        sync_config_brightness_fn=sync_config,
    )

    sync_config.assert_not_called()


class TestApplyBrightnessPolicySeam:
    def test_negative_brightness_is_noop(self) -> None:
        from src.core.power.management._manager_brightness_execution import apply_brightness_policy

        run_boundary = MagicMock()
        apply_brightness_policy(
            MagicMock(), -1,
            run_boundary_fn=run_boundary,
            sync_config_fn=MagicMock(),
        )
        run_boundary.assert_not_called()

    def test_zero_brightness_enters_boundary(self) -> None:
        from src.core.power.management._manager_brightness_execution import apply_brightness_policy

        invoked = []

        def _boundary(action, *, log_message, fallback=None):
            invoked.append(log_message)
            action()

        apply_brightness_policy(
            MagicMock(spec=[]),  # no hook, no engine → noop inside
            0,
            run_boundary_fn=_boundary,
            sync_config_fn=MagicMock(),
        )
        assert invoked == ["Battery saver brightness apply failed"]

    def test_delegates_classify_and_execute_via_boundary(self) -> None:
        from src.core.power.management._manager_brightness_execution import apply_brightness_policy

        kb = MagicMock()
        kb.apply_brightness_from_power_policy = MagicMock()
        sync_config = MagicMock()

        def _boundary(action, *, log_message, fallback=None):
            return action()

        apply_brightness_policy(
            kb, 80,
            run_boundary_fn=_boundary,
            sync_config_fn=sync_config,
        )
        kb.apply_brightness_from_power_policy.assert_called_once_with(80)
        sync_config.assert_not_called()


class TestSyncConfigBrightnessSeam:
    def test_sets_brightness_on_config(self) -> None:
        from src.core.power.management._manager_brightness_execution import sync_config_brightness

        config = MagicMock()
        log = MagicMock()
        sync_config_brightness(config, 55, logger=log)
        assert config.brightness == 55

    def test_logs_warning_on_runtime_error(self) -> None:
        from src.core.power.management._manager_brightness_execution import sync_config_brightness

        class _BadConfig:
            @property
            def brightness(self):
                return 0

            @brightness.setter
            def brightness(self, _):
                raise RuntimeError("fail")

        log = MagicMock()
        sync_config_brightness(_BadConfig(), 30, logger=log)
        log.warning.assert_called_once()