from __future__ import annotations

from types import SimpleNamespace
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
    assert plan.sync_engine_perkey_brightness is False

    def _sync_config(brightness: int) -> None:
        call_order.append(("sync", brightness))

    execute_brightness_execution(
        plan=plan,
        sync_config_brightness_fn=_sync_config,
    )

    assert call_order == [("sync", 75), ("engine", 75)]


def test_classify_engine_fallback_marks_perkey_sync_for_base_only_state() -> None:
    kb_controller = MagicMock()
    del kb_controller.apply_brightness_from_power_policy
    kb_controller.engine = MagicMock()
    config = SimpleNamespace(effect="none", per_key_colors={(0, 0): (1, 2, 3)})

    plan = classify_brightness_execution(kb_controller=kb_controller, brightness=30, config=config)

    assert plan.sync_engine_perkey_brightness is True


def test_execute_brightness_engine_fallback_syncs_engine_perkey_brightness_when_requested() -> None:
    engine = MagicMock()
    plan = classify_brightness_execution(
        kb_controller=SimpleNamespace(engine=engine),
        brightness=45,
        config=SimpleNamespace(effect="reactive_ripple", per_key_colors={}),
    )

    execute_brightness_execution(
        plan=plan,
        sync_config_brightness_fn=MagicMock(),
    )

    assert engine.per_key_brightness == 45
    engine.set_brightness.assert_called_once_with(45)


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
            config=MagicMock(),
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
            config=MagicMock(),
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
            config=MagicMock(),
            sync_config_fn=sync_config,
        )
        kb.apply_brightness_from_power_policy.assert_called_once_with(80)
        sync_config.assert_not_called()


class TestSyncConfigBrightnessSeam:
    def test_sets_global_brightness_on_non_perkey_config(self) -> None:
        from src.core.power.management._manager_brightness_execution import sync_config_brightness

        class _Config:
            def __init__(self) -> None:
                self.effect = "wave"
                self.brightness = 10
                self.perkey_brightness = 20
                self.per_key_colors = {}

            @property
            def effect_brightness(self):
                return self.brightness

            @effect_brightness.setter
            def effect_brightness(self, value):
                self.brightness = value

        config = _Config()
        log = MagicMock()
        sync_config_brightness(config, 55, logger=log)
        assert config.effect_brightness == 55
        assert config.brightness == 55
        assert config.perkey_brightness == 20

    def test_sets_global_and_perkey_brightness_for_base_only_state(self) -> None:
        from src.core.power.management._manager_brightness_execution import sync_config_brightness

        class _Config:
            def __init__(self) -> None:
                self.effect = "none"
                self._effect_brightness = 10
                self.perkey_brightness = 20
                self.per_key_colors = {(0, 0): (1, 2, 3)}

            @property
            def brightness(self):
                return self.perkey_brightness

            @brightness.setter
            def brightness(self, value):
                self.perkey_brightness = value

            @property
            def effect_brightness(self):
                return self._effect_brightness

            @effect_brightness.setter
            def effect_brightness(self, value):
                self._effect_brightness = value

        config = _Config()
        log = MagicMock()
        sync_config_brightness(config, 35, logger=log)
        assert config.effect_brightness == 35
        assert config.brightness == 35
        assert config.perkey_brightness == 35

    def test_logs_warning_on_runtime_error(self) -> None:
        from src.core.power.management._manager_brightness_execution import sync_config_brightness

        class _BadConfig:
            effect = "wave"
            per_key_colors = {}

            @property
            def effect_brightness(self):
                return 0

            @effect_brightness.setter
            def effect_brightness(self, _):
                raise RuntimeError("fail")

        log = MagicMock()
        sync_config_brightness(_BadConfig(), 30, logger=log)
        log.warning.assert_called_once()
