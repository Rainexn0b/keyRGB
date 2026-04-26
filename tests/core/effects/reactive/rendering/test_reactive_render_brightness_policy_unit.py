from __future__ import annotations

import logging

from types import SimpleNamespace

import pytest


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyKB:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        self.calls.append(("set_brightness", int(brightness)))

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
        self.calls.append(("set_key_colors", int(brightness)))


def test_reactive_render_caps_hw_brightness_to_engine_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,
        _dim_temp_active=True,
        per_key_colors={(0, 0): (255, 0, 0)},
        per_key_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("enable_user_mode", 5) in kb.calls
    assert ("set_key_colors", 5) in kb.calls


def test_reactive_render_caps_hw_brightness_to_policy_cap_without_dim_flag() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=3,
        reactive_brightness=50,
        _hw_brightness_cap=3,
        per_key_colors={(0, 0): (255, 0, 0)},
        per_key_brightness=3,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("enable_user_mode", 3) in kb.calls
    assert ("set_key_colors", 3) in kb.calls


def test_reactive_render_ramps_from_zero_when_last_rendered_brightness_is_none() -> None:
    from src.core.effects.reactive.render import _MAX_BRIGHTNESS_STEP_PER_FRAME, render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=1,
        reactive_brightness=25,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=25,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=None,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    written = [brightness for (op, brightness) in kb.calls if op == "set_key_colors"]
    assert written, "expected at least one set_key_colors call"
    assert written[0] <= _MAX_BRIGHTNESS_STEP_PER_FRAME


def test_render_guard_bypassed_for_dim_temp_downward_jump() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,
        reactive_brightness=50,
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,
        _dim_temp_active=True,
        _last_rendered_brightness=50,
        _last_hw_mode_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    written = [brightness for (op, brightness) in kb.calls if op == "set_brightness"]
    assert written, "expected a set_brightness call on first dim frame"
    assert written[0] == 5


def test_render_guard_still_active_for_upward_jumps_under_dim_temp() -> None:
    from src.core.effects.reactive.render import _MAX_BRIGHTNESS_STEP_PER_FRAME, render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=50,
        reactive_brightness=50,
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,
        _dim_temp_active=True,
        _last_rendered_brightness=5,
        _last_hw_mode_brightness=5,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    written = [brightness for (op, brightness) in kb.calls if op == "set_brightness"]
    assert written, "expected a set_brightness call"
    assert written[0] <= 5 + _MAX_BRIGHTNESS_STEP_PER_FRAME


def test_per_key_reactive_pulse_respects_dim_temp_lock() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=True,
        _reactive_active_pulse_mix=1.0,
        _last_rendered_brightness=5,
        _last_hw_mode_brightness=5,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("set_key_colors", 5) in kb.calls
    assert not [call for call in kb.calls if call == ("set_brightness", 50)]


def test_render_logs_visual_scale_under_debug(monkeypatch, caplog) -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=5,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=0.709,
        _reactive_debug_last_pulse_scale=1.0,
        _last_rendered_brightness=5,
        _last_hw_mode_brightness=5,
    )

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")

    with caplog.at_level(logging.INFO, logger="src.core.effects.reactive.render"):
        render(engine, color_map={(0, 0): (255, 255, 255)})

    messages = [record.getMessage() for record in caplog.records if "reactive_render_visual:" in record.getMessage()]
    assert messages
    assert "pulse_scale=1.000" in messages[-1]
    assert "transition_scale=1.000" in messages[-1]
    assert "combined_scale=1.000" in messages[-1]


def test_resolve_brightness_logs_traceback_when_engine_attr_read_raises(caplog) -> None:
    from src.core.effects.reactive import render as render_module

    class _BrokenEngine:
        brightness = 7
        per_key_colors = None
        per_key_brightness = 0
        _hw_brightness_cap = None
        _dim_temp_active = False
        _last_rendered_brightness = None
        kb = None

        @property
        def reactive_brightness(self):
            raise RuntimeError("reactive getter failed")

    with caplog.at_level(logging.ERROR, logger="src.core.effects.reactive.render"):
        base, eff, hw = render_module._resolve_brightness(_BrokenEngine())

    assert (base, eff, hw) == (0, 25, 7)

    records = [
        record
        for record in caplog.records
        if "Reactive brightness failed to read engine attribute reactive_brightness" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_resolve_brightness_propagates_unexpected_engine_attr_read_errors() -> None:
    from src.core.effects.reactive import render as render_module

    class _BrokenEngine:
        brightness = 7
        per_key_colors = None
        per_key_brightness = 0
        _hw_brightness_cap = None
        _dim_temp_active = False
        _last_rendered_brightness = None
        kb = None

        @property
        def reactive_brightness(self):
            raise AssertionError("unexpected reactive getter bug")

    with pytest.raises(AssertionError, match="unexpected reactive getter bug"):
        render_module._resolve_brightness(_BrokenEngine())


def test_clear_transition_state_logs_runtime_setter_failures(caplog) -> None:
    from src.core.effects.reactive._render_brightness import _clear_transition_state

    class _BrokenEngine:
        def __setattr__(self, name, value):
            del value
            if name == "_reactive_transition_to_brightness":
                raise RuntimeError("setter failed")
            object.__setattr__(self, name, None)

    engine = _BrokenEngine()

    with caplog.at_level(logging.ERROR, logger="src.core.effects.reactive._render_brightness"):
        _clear_transition_state(engine)

    records = [
        record
        for record in caplog.records
        if "Reactive brightness failed to clear engine attribute _reactive_transition_to_brightness"
        in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_clear_transition_state_propagates_unexpected_setter_failures() -> None:
    from src.core.effects.reactive._render_brightness import _clear_transition_state

    class _BrokenEngine:
        def __setattr__(self, name, value):
            del value
            if name == "_reactive_transition_to_brightness":
                raise AssertionError("unexpected setter bug")
            object.__setattr__(self, name, None)

    with pytest.raises(AssertionError, match="unexpected setter bug"):
        _clear_transition_state(_BrokenEngine())


def test_set_uniform_hw_streak_clamps_negative_values_to_zero() -> None:
    from src.core.effects.reactive._render_brightness_support import set_uniform_hw_streak

    engine = SimpleNamespace(_reactive_uniform_hw_streak=9)

    set_uniform_hw_streak(engine, value=-4, logger=logging.getLogger("test"))

    assert engine._reactive_uniform_hw_streak == 0
