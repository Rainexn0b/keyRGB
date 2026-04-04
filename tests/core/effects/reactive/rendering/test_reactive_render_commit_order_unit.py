from __future__ import annotations

import pytest

from types import SimpleNamespace


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyKB:
    def __init__(self, *, set_brightness_exc: Exception | None = None):
        self.calls: list[tuple[str, int]] = []
        self._set_brightness_exc = set_brightness_exc

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        if self._set_brightness_exc is not None:
            raise self._set_brightness_exc
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


def test_apply_hw_brightness_reinitializes_user_mode_for_recoverable_runtime_errors() -> None:
    from src.core.effects.reactive._render_runtime import apply_hw_brightness

    kb = _DummyKB(set_brightness_exc=OSError("boom"))
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        _last_hw_mode_brightness=8,
    )

    apply_hw_brightness(engine, 16)

    assert kb.calls == [("enable_user_mode", 16)]
    assert engine._last_hw_mode_brightness == 16


def test_apply_hw_brightness_propagates_unexpected_brightness_errors() -> None:
    from src.core.effects.reactive._render_runtime import apply_hw_brightness

    class UnexpectedBrightnessError(Exception):
        pass

    kb = _DummyKB(set_brightness_exc=UnexpectedBrightnessError("boom"))
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        _last_hw_mode_brightness=8,
    )

    with pytest.raises(UnexpectedBrightnessError):
        apply_hw_brightness(engine, 16)

    assert kb.calls == []
    assert engine._last_hw_mode_brightness == 8
