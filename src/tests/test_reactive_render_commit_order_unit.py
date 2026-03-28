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


def test_render_uses_set_brightness_after_first_frame() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=8,
        reactive_brightness=8,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=8,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=8,
        _last_hw_mode_brightness=8,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})
    assert not [call for call in kb.calls if call[0] == "enable_user_mode"]
    assert not [call for call in kb.calls if call[0] == "set_brightness"]

    kb.calls.clear()
    engine.brightness = 16
    engine.reactive_brightness = 16
    engine.per_key_brightness = 16
    engine._last_rendered_brightness = 8

    render(engine, color_map={(0, 0): (255, 255, 255)})

    enable_calls = [call for call in kb.calls if call[0] == "enable_user_mode"]
    set_brightness_calls = [call for call in kb.calls if call[0] == "set_brightness"]
    assert not enable_calls
    assert len(set_brightness_calls) == 1


def test_render_uses_enable_user_mode_on_first_frame() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=8,
        reactive_brightness=8,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=8,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=0,
        _last_hw_mode_brightness=None,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    enable_calls = [call for call in kb.calls if call[0] == "enable_user_mode"]
    assert len(enable_calls) == 1


def test_render_set_brightness_always_after_data_when_dimming() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=42,
        reactive_brightness=42,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=42,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=50,
        _last_hw_mode_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    ops = [op for (op, _brightness) in kb.calls]
    assert "set_key_colors" in ops
    assert "set_brightness" in ops
    assert ops.index("set_key_colors") < ops.index("set_brightness")


def test_render_set_brightness_after_data_when_brightening() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=16,
        reactive_brightness=16,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=16,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=8,
        _last_hw_mode_brightness=8,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    ops = [op for (op, _brightness) in kb.calls]
    assert "set_key_colors" in ops
    assert "set_brightness" in ops
    assert ops.index("set_key_colors") < ops.index("set_brightness")