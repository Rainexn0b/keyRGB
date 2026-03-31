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


def test_sw_render_subsequent_per_key_frame_reasserts_user_mode() -> None:
    """Every frame re-asserts user mode so the ITE controller cannot drift back
    to a saved hardware effect between frames."""
    engine = _mk_engine(brightness=25, last_hw_mode_brightness=25)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 25),
        ("set_key_colors", 25),
    ]
    assert engine._last_hw_mode_brightness == 25


def test_sw_render_brightness_change_uses_enable_user_mode_with_new_brightness() -> None:
    """When brightness changes, the new value is carried by enable_user_mode
    (SET_EFFECT), not a separate SET_BRIGHTNESS call."""
    engine = _mk_engine(brightness=30, last_hw_mode_brightness=25)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 30),
        ("set_key_colors", 30),
    ]
    assert engine._last_hw_mode_brightness == 30


def test_sw_render_every_frame_calls_enable_user_mode_regardless_of_brightness_history() -> None:
    """Whether _last_hw_mode_brightness is None, equal, or different from the
    current brightness, enable_user_mode is always called before set_key_colors."""
    for last_hw in (None, 10, 25, 50):
        engine = _mk_engine(brightness=25, last_hw_mode_brightness=last_hw)
        sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})
        assert engine.kb.calls == [
            ("enable_user_mode", 25),
            ("set_key_colors", 25),
        ], f"Failed for last_hw_mode_brightness={last_hw}"
        assert engine._last_hw_mode_brightness == 25


def test_sw_render_enable_user_mode_called_on_every_consecutive_frame() -> None:
    """Regression: in the 0.19.0 post-release window, render() only called
    enable_user_mode on the first frame.  The ITE 8291r3 controller reverts to
    its saved hardware effect between user-mode frames, causing the effect to
    'bounce randomly between colors' rather than animating smoothly.

    This test would have caught the regression: after the first frame,
    subsequent frames must still emit enable_user_mode before set_key_colors.
    """
    engine = _mk_engine(brightness=25, last_hw_mode_brightness=None)

    for frame in range(5):
        sw_base.render(engine, color_map={(0, 0): (255, frame, 0)})

    # Every single frame must have called enable_user_mode then set_key_colors.
    assert len(engine.kb.calls) == 10
    for i in range(5):
        assert engine.kb.calls[i * 2] == ("enable_user_mode", 25), f"frame {i} missing enable_user_mode"
        assert engine.kb.calls[i * 2 + 1] == ("set_key_colors", 25), f"frame {i} missing set_key_colors"