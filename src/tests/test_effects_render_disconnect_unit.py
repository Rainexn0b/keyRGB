from __future__ import annotations

from threading import RLock
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.core.effects.reactive import render as reactive_render
from src.core.effects.software import base as sw_base


class Errno19(Exception):
    def __init__(self, message: str = "No such device"):
        super().__init__(message)
        self.errno = 19


def _mk_engine(*, key_colors_exc: Exception):
    kb = SimpleNamespace(
        enable_user_mode=lambda **_k: None,
        set_key_colors=MagicMock(side_effect=key_colors_exc),
        set_color=MagicMock(),
    )
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=RLock(),
        brightness=25,
        speed=4,
        current_color=(255, 0, 0),
        per_key_colors=None,
        mark_device_unavailable=MagicMock(),
    )
    return engine


def test_sw_render_disconnect_marks_unavailable_and_skips_uniform_fallback() -> None:
    engine = _mk_engine(key_colors_exc=Errno19())

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    engine.mark_device_unavailable.assert_called_once()
    assert engine.kb.set_color.call_count == 0


def test_reactive_render_disconnect_marks_unavailable_and_skips_uniform_fallback() -> None:
    engine = _mk_engine(key_colors_exc=Errno19())

    reactive_render.render(engine, color_map={(0, 0): (255, 0, 0)})

    engine.mark_device_unavailable.assert_called_once()
    assert engine.kb.set_color.call_count == 0


def test_sw_render_non_disconnect_error_falls_back_to_uniform() -> None:
    engine = _mk_engine(key_colors_exc=RuntimeError("boom"))

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    engine.mark_device_unavailable.assert_not_called()
    assert engine.kb.set_color.call_count == 1
