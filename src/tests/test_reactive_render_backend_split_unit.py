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


class _DummyUniformKB:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        self.calls.append(("set_brightness", int(brightness)))

    def set_color(self, _rgb, *, brightness: int):
        self.calls.append(("set_color", int(brightness)))


def test_per_key_reactive_pulse_keeps_hw_at_profile_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=1.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("set_key_colors", 15) in kb.calls
    assert not [call for call in kb.calls if call[0] == "set_brightness"]


def test_per_key_reactive_pulse_first_frame_initializes_mode_at_profile_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=1.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=None,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("enable_user_mode", 15) in kb.calls
    assert ("set_key_colors", 15) in kb.calls
    assert not [call for call in kb.calls if call[0] == "set_brightness"]


def test_uniform_reactive_pulse_can_still_lift_hw_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyUniformKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=1.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("set_color", 50) in kb.calls
    assert ("set_brightness", 50) in kb.calls


def test_uniform_reactive_pulse_returns_directly_to_idle_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyUniformKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=0.0,
        _last_rendered_brightness=50,
        _last_hw_mode_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("set_color", 15) in kb.calls
    assert ("set_brightness", 15) in kb.calls
