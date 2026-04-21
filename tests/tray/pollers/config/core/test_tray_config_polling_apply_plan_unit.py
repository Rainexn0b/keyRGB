from __future__ import annotations

import pytest

from src.tray.pollers.config_polling_internal._apply_plan import (
    ConfigApplyPlan,
    classify_config_apply_plan,
)
from src.tray.pollers.config_polling_internal.core import ConfigApplyState


def _mk_state(*, effect: str = "rainbow_wave", brightness: int = 25) -> ConfigApplyState:
    return ConfigApplyState(
        effect=effect,
        speed=4,
        brightness=brightness,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )


def test_persist_effect_is_none_when_effects_match() -> None:
    state = _mk_state(effect="rainbow_wave", brightness=25)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.persist_effect is None


def test_persist_effect_equals_current_effect_when_effects_differ() -> None:
    state = _mk_state(effect="static", brightness=25)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.persist_effect == "static"


def test_execution_kind_is_turn_off_when_brightness_zero() -> None:
    state = _mk_state(effect="rainbow_wave", brightness=0)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.execution_kind == "turn_off"


def test_execution_kind_is_apply_when_brightness_positive() -> None:
    state = _mk_state(effect="rainbow_wave", brightness=1)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.execution_kind == "apply"
