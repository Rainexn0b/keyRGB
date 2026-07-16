from __future__ import annotations

from src.tray.pollers.config_polling_internal._apply_plan import (
    classify_apply_mode,
    classify_config_apply_plan,
    should_skip_config_apply_for_power_source_transition,
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


def test_persist_effect_uses_selected_effect_not_runtime_render_effect() -> None:
    state = ConfigApplyState(
        effect="perkey",
        selected_effect="none",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=(((0, 0), (1, 2, 3)),),
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    plan = classify_config_apply_plan(configured_effect="none", current=state)
    assert plan.persist_effect is None


def test_execution_kind_is_turn_off_when_brightness_zero() -> None:
    state = _mk_state(effect="rainbow_wave", brightness=0)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.execution_kind == "turn_off"


def test_execution_kind_is_apply_when_brightness_positive() -> None:
    state = _mk_state(effect="rainbow_wave", brightness=1)
    plan = classify_config_apply_plan(configured_effect="rainbow_wave", current=state)
    assert plan.execution_kind == "apply"


def test_classify_apply_mode_maps_effect_names() -> None:
    assert classify_apply_mode("perkey") == "perkey"
    assert classify_apply_mode("none") == "uniform"
    assert classify_apply_mode("rainbow_wave") == "effect"
    assert classify_apply_mode("reactive_fade") == "effect"


def test_apply_mode_is_classified_on_plan() -> None:
    assert classify_config_apply_plan(
        configured_effect="perkey", current=_mk_state(effect="perkey")
    ).apply_mode == "perkey"
    assert classify_config_apply_plan(
        configured_effect="none", current=_mk_state(effect="none")
    ).apply_mode == "uniform"
    assert classify_config_apply_plan(
        configured_effect="rainbow_wave", current=_mk_state(effect="rainbow_wave", brightness=0)
    ).apply_mode == "effect"


def test_skip_power_source_transition_only_for_perkey_mtime() -> None:
    perkey = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=(((0, 0), (1, 2, 3)),),
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    uniform = _mk_state(effect="none")
    assert (
        should_skip_config_apply_for_power_source_transition(
            cause="mtime_change",
            current=perkey,
            recent_power_source_transition=True,
        )
        is True
    )
    assert (
        should_skip_config_apply_for_power_source_transition(
            cause="poll",
            current=perkey,
            recent_power_source_transition=True,
        )
        is False
    )
    assert (
        should_skip_config_apply_for_power_source_transition(
            cause="mtime_change",
            current=uniform,
            recent_power_source_transition=True,
        )
        is False
    )
    assert (
        should_skip_config_apply_for_power_source_transition(
            cause="mtime_change",
            current=perkey,
            recent_power_source_transition=False,
        )
        is False
    )
