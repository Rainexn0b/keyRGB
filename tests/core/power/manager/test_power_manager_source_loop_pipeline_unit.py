"""Pipeline seam tests: build_power_source_loop_inputs → PowerSourceLoopPolicy.update()."""

from __future__ import annotations

from datetime import datetime as _datetime, timezone
from unittest.mock import MagicMock

import pytest

import keyrgb.core.power.management._manager_helpers as manager_helpers
from keyrgb.core.power.system import PowerMode


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
    from keyrgb.core.power.management._manager_helpers import (
        apply_power_source_actions,
        build_power_source_loop_inputs,
    )
    from keyrgb.core.power.policies.power_source_loop_policy import PowerSourceLoopPolicy

    _values = {"brightness": 50, "battery_saver_brightness": 25}

    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _FakeConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.BALANCED),
        get_active_perkey_profile_fn=lambda: "default",
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
        activate_power_mode=MagicMock(),
        activate_perkey_profile=MagicMock(),
    )

    kb.turn_off.assert_not_called()


def test_pipeline_emits_power_mode_activation_for_configured_ac_mode() -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import ActivatePowerMode, PowerSourceLoopPolicy

    class _PowerModeConfig(_FakeConfig):
        ac_power_mode = PowerMode.BALANCED.value

    values = {"brightness": 50, "battery_saver_brightness": 25}
    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _PowerModeConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.PERFORMANCE),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None

    result = PowerSourceLoopPolicy(debounce_seconds=0.0).update(inputs)

    assert ActivatePowerMode(PowerMode.BALANCED) in result.actions


def test_pipeline_emits_battery_power_mode_when_battery_lighting_is_disabled() -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import (
        ActivatePowerMode,
        PowerSourceLoopPolicy,
        TurnOffKeyboard,
    )

    class _BatteryPowerModeConfig(_FakeConfig):
        ac_power_mode = PowerMode.PERFORMANCE.value
        battery_power_mode = PowerMode.EXTREME_SAVER.value
        battery_lighting_enabled = False

    values = {"brightness": 40, "battery_saver_brightness": 25}
    kb = MagicMock()
    kb.is_off = False

    policy = PowerSourceLoopPolicy(debounce_seconds=0.0)
    ac_inputs = build_power_source_loop_inputs(
        _BatteryPowerModeConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.PERFORMANCE),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )
    battery_inputs = build_power_source_loop_inputs(
        _BatteryPowerModeConfig(),
        kb_controller=kb,
        on_ac=False,
        now_mono=1010.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.PERFORMANCE),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert ac_inputs is not None
    assert battery_inputs is not None

    _ = policy.update(ac_inputs)
    result = policy.update(battery_inputs)

    assert TurnOffKeyboard() in result.actions
    assert ActivatePowerMode(PowerMode.EXTREME_SAVER) in result.actions


def test_pipeline_on_ac_at_night_uses_scheduler_night_brightness(monkeypatch: pytest.MonkeyPatch) -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import ApplyBrightness, PowerSourceLoopPolicy

    class _NightConfig(_FakeConfig):
        time_scheduler_enabled = True
        day_start_time = "08:00"
        night_start_time = "20:00"
        night_base_brightness = 20
        ac_lighting_brightness = 25

    class FakeDateTime:
        @staticmethod
        def now() -> _datetime:
            return _datetime(2024, 1, 1, 22, 24, tzinfo=timezone.utc)

    monkeypatch.setattr(manager_helpers, "datetime", FakeDateTime)

    values = {
        "brightness": 25,
        "battery_saver_brightness": 25,
        "night_base_brightness": 20,
    }

    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _NightConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.BALANCED),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None

    result = PowerSourceLoopPolicy().update(inputs)

    assert result.actions == (ApplyBrightness(20),)


def test_pipeline_on_ac_by_day_keeps_power_source_brightness_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import ApplyBrightness, PowerSourceLoopPolicy

    class _DayConfig(_FakeConfig):
        time_scheduler_enabled = True
        day_start_time = "08:00"
        night_start_time = "20:00"
        day_base_brightness = 30
        ac_lighting_brightness = 45

    class FakeDateTime:
        @staticmethod
        def now() -> _datetime:
            return _datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(manager_helpers, "datetime", FakeDateTime)

    values = {
        "brightness": 30,
        "battery_saver_brightness": 25,
        "day_base_brightness": 30,
    }

    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _DayConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.BALANCED),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None

    result = PowerSourceLoopPolicy().update(inputs)

    assert result.actions == (ApplyBrightness(45),)


def test_pipeline_on_ac_by_day_uses_scheduler_brightness_when_active_power_source_brightness_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import ApplyBrightness, PowerSourceLoopPolicy

    class _DayFallbackConfig(_FakeConfig):
        time_scheduler_enabled = True
        day_start_time = "08:00"
        night_start_time = "20:00"
        day_base_brightness = 30
        ac_lighting_brightness = None
        battery_lighting_brightness = 15

    class FakeDateTime:
        @staticmethod
        def now() -> _datetime:
            return _datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(manager_helpers, "datetime", FakeDateTime)

    values = {
        "brightness": 45,
        "battery_saver_brightness": 25,
        "day_base_brightness": 30,
    }

    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _DayFallbackConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.BALANCED),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None

    result = PowerSourceLoopPolicy().update(inputs)

    assert result.actions == (ApplyBrightness(30),)


def test_pipeline_emits_perkey_profile_activation_for_configured_ac_profile() -> None:
    from keyrgb.core.power.management._manager_helpers import build_power_source_loop_inputs
    from keyrgb.core.power.policies.power_source_loop_policy import ActivatePerkeyProfile, PowerSourceLoopPolicy

    class _PerkeyProfileConfig(_FakeConfig):
        ac_perkey_profile_name = "gaming"

    values = {"brightness": 50, "battery_saver_brightness": 25}
    kb = MagicMock()
    kb.is_off = False

    inputs = build_power_source_loop_inputs(
        _PerkeyProfileConfig(),
        kb_controller=kb,
        on_ac=True,
        now_mono=1000.0,
        get_power_mode_status_fn=lambda: MagicMock(supported=True, mode=PowerMode.BALANCED),
        get_active_perkey_profile_fn=lambda: "default",
        safe_int_attr_fn=lambda obj, name, default=0: values.get(name, default),
    )

    assert inputs is not None

    result = PowerSourceLoopPolicy(debounce_seconds=0.0).update(inputs)

    assert ActivatePerkeyProfile("gaming") in result.actions
