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
        # Called by enable_user_mode_once
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
        self.calls.append(("set_key_colors", int(brightness)))


def test_reactive_render_caps_hw_brightness_to_engine_brightness() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB()

    # per_key_colors set => base channel active; per_key_brightness higher than engine.brightness
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,
        _dim_temp_active=True,
        per_key_colors={(0, 0): (255, 0, 0)},
        per_key_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    # In temp-dim mode, both calls should use brightness=engine.brightness (5).
    assert ("enable_user_mode", 5) in kb.calls
    assert ("set_key_colors", 5) in kb.calls
