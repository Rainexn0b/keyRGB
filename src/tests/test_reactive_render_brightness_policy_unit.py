from __future__ import annotations

from types import SimpleNamespace


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
