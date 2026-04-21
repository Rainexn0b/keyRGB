from __future__ import annotations

from types import SimpleNamespace

from src.core.effects.catalog import REACTIVE_EFFECTS
from src.tray.pollers.config_polling_internal.core import ConfigApplyState
from src.tray.pollers.config_polling_internal.core import classify_apply_from_config
from src.tray.pollers.config_polling_internal.core import compute_config_apply_state


def _mk_tray(*, effect: str = "static", speed: int = 4, brightness: int = 30, color=(0, 255, 0)):
    config = SimpleNamespace(
        effect=effect,
        speed=speed,
        brightness=brightness,
        color=color,
        per_key_colors=None,
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
        reactive_brightness=brightness,
        reactive_trail_percent=50,
        software_effect_target="keyboard",
    )
    return SimpleNamespace(config=config, backend=None)


def test_compute_config_apply_state_reads_static_effect_config() -> None:
    tray = _mk_tray(effect="static", speed=3, brightness=40, color=(255, 0, 0))

    state = compute_config_apply_state(tray)

    assert state == ConfigApplyState(
        effect="static",
        speed=3,
        brightness=40,
        color=(255, 0, 0),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        reactive_brightness=0,
        reactive_trail_percent=50,
        software_effect_target="keyboard",
    )


def test_compute_config_apply_state_reads_reactive_effect_fields() -> None:
    reactive_effect = REACTIVE_EFFECTS[0]
    tray = _mk_tray(effect=reactive_effect, speed=5, brightness=35, color=(5, 6, 7))
    tray.config.reactive_brightness = 22
    tray.config.reactive_trail_percent = 73

    state = compute_config_apply_state(tray)

    assert state.effect == reactive_effect
    assert state.brightness == 35
    assert state.reactive_brightness == 22
    assert state.reactive_trail_percent == 73
    assert state.reactive_color == (10, 20, 30)


def test_compute_config_apply_state_falls_back_to_none_when_effect_read_raises() -> None:
    class BrokenConfig:
        speed = 4
        brightness = 30
        color = (1, 2, 3)
        per_key_colors = None
        reactive_use_manual_color = False
        reactive_color = (10, 20, 30)
        reactive_brightness = 30
        reactive_trail_percent = 50
        software_effect_target = "keyboard"

        @property
        def effect(self) -> str:
            raise RuntimeError("boom")

    tray = SimpleNamespace(config=BrokenConfig(), backend=None)

    state = compute_config_apply_state(tray)

    assert state.effect == "none"


def test_compute_then_classify_same_effect_does_not_require_persist() -> None:
    tray = _mk_tray(effect="static", speed=3, brightness=40, color=(255, 0, 0))

    state = compute_config_apply_state(tray)
    plan = classify_apply_from_config(configured_effect=state.effect, current=state)

    assert plan.persist_effect is None


def test_compute_then_classify_effect_change_persists_current_effect() -> None:
    tray = _mk_tray(effect="wave", speed=4, brightness=30, color=(4, 5, 6))

    state = compute_config_apply_state(tray)
    plan = classify_apply_from_config(configured_effect="static", current=state)

    assert plan.persist_effect == "wave"


def test_compute_then_classify_zero_brightness_returns_turn_off_plan() -> None:
    tray = _mk_tray(effect="static", speed=3, brightness=0, color=(255, 0, 0))

    state = compute_config_apply_state(tray)
    plan = classify_apply_from_config(configured_effect=state.effect, current=state)

    assert plan.execution_kind == "turn_off"