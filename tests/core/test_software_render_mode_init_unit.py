from __future__ import annotations

from types import SimpleNamespace

from src.core.effects.software import base as sw_base


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyPerKeyKB:
    def __init__(self, *, fail_set_brightness: bool = False):
        self.calls: list[tuple[str, int]] = []
        self._fail_set_brightness = bool(fail_set_brightness)

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        del save
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        if self._fail_set_brightness:
            raise OSError("boom")
        self.calls.append(("set_brightness", int(brightness)))

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
        assert enable_user_mode is False
        self.calls.append(("set_key_colors", int(brightness)))


def _mk_engine(*, brightness: int = 25, last_hw_mode_brightness=None, fail_set_brightness: bool = False):
    kb = _DummyPerKeyKB(fail_set_brightness=fail_set_brightness)
    return SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=brightness,
        speed=4,
        current_color=(255, 0, 0),
        per_key_colors={(0, 0): (255, 255, 255)},
        mark_device_unavailable=lambda: None,
        _last_hw_mode_brightness=last_hw_mode_brightness,
    )


def test_sw_render_first_per_key_frame_initializes_mode_once() -> None:
    engine = _mk_engine(brightness=25, last_hw_mode_brightness=None)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 25),
        ("set_key_colors", 25),
    ]
    assert engine._last_hw_mode_brightness == 25


def test_sw_render_subsequent_per_key_frame_skips_mode_reinit() -> None:
    engine = _mk_engine(brightness=25, last_hw_mode_brightness=25)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("set_key_colors", 25),
    ]
    assert engine._last_hw_mode_brightness == 25


def test_sw_render_brightness_change_uses_set_brightness_without_reinit() -> None:
    engine = _mk_engine(brightness=30, last_hw_mode_brightness=25)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("set_key_colors", 30),
        ("set_brightness", 30),
    ]
    assert engine._last_hw_mode_brightness == 30


def test_sw_render_brightness_change_falls_back_to_mode_init_when_needed() -> None:
    engine = _mk_engine(brightness=30, last_hw_mode_brightness=25, fail_set_brightness=True)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("set_key_colors", 30),
        ("enable_user_mode", 30),
    ]
    assert engine._last_hw_mode_brightness == 30