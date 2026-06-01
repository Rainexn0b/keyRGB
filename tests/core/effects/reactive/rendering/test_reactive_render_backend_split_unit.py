from __future__ import annotations

from types import SimpleNamespace


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyKB:
    def __init__(self, *, per_key_mode_policy: str = "init_once"):
        self.calls: list[tuple[str, int]] = []
        self.frames: list[dict[tuple[int, int], tuple[int, int, int]]] = []
        self.keyrgb_per_key_mode_policy = str(per_key_mode_policy)

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        self.calls.append(("set_brightness", int(brightness)))

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
        self.frames.append(dict(_color_map))
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


def test_per_key_reactive_reassert_policy_reinitializes_each_frame() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB(per_key_mode_policy="reassert_every_frame")
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
        _reactive_uniform_hw_streak=6,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert ("enable_user_mode", 15) in kb.calls
    assert ("set_key_colors", 15) in kb.calls
    assert not [call for call in kb.calls if call[0] == "set_brightness"]


def test_per_key_reactive_init_once_policy_skips_duplicate_idle_frame() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB(per_key_mode_policy="init_once")
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=0.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
        _last_reactive_per_key_frame_signature=None,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})
    assert kb.calls == [
        ("set_key_colors", 15),
    ]

    kb.calls.clear()
    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert kb.calls == []


def test_per_key_reactive_reassert_policy_reinitializes_duplicate_idle_frame() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB(per_key_mode_policy="reassert_every_frame")
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=0.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
        _last_reactive_per_key_frame_signature=None,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})
    kb.calls.clear()

    render(engine, color_map={(0, 0): (255, 255, 255)})

    assert kb.calls == [
        ("enable_user_mode", 15),
        ("set_key_colors", 15),
    ]


def test_per_key_reactive_duplicate_frame_cache_keeps_animating_changed_frames() -> None:
    from src.core.effects.reactive.render import render

    kb = _DummyKB(per_key_mode_policy="reassert_every_frame")
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
        _last_reactive_per_key_frame_signature=None,
    )

    render(engine, color_map={(0, 0): (255, 0, 0)})
    kb.calls.clear()

    render(engine, color_map={(0, 0): (255, 1, 0)})

    assert kb.calls == [
        ("enable_user_mode", 15),
        ("set_key_colors", 15),
    ]


def test_per_key_reactive_logs_deck_scale_frame_changes_when_debug_enabled(monkeypatch) -> None:
    import src.core.effects.reactive.render as reactive_render
    from src.core.effects.reactive.render import render

    kb = _DummyKB(per_key_mode_policy="init_once")
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=15,
        reactive_brightness=50,
        per_key_colors={(0, 0): (255, 0, 0), (0, 1): (255, 0, 0), (0, 2): (255, 0, 0), (0, 3): (255, 0, 0)},
        per_key_brightness=15,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _reactive_active_pulse_mix=1.0,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
        _last_reactive_per_key_frame_signature=None,
    )

    logged: list[str] = []
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr(reactive_render.logger, "info", lambda message, *args: logged.append(message % args))

    first_frame = {(0, 0): (255, 0, 0), (0, 1): (255, 0, 0), (0, 2): (255, 0, 0), (0, 3): (255, 0, 0)}
    second_frame = {(0, 0): (0, 255, 0), (0, 1): (0, 255, 0), (0, 2): (0, 255, 0), (0, 3): (0, 255, 0)}

    render(engine, color_map=first_frame)
    logged.clear()

    render(engine, color_map=second_frame)

    assert any(
        "reactive_frame_deck_change" in entry
        and "changed_keys=4" in entry
        and "total_keys=4" in entry
        and "lit_keys=4" in entry
        and "brightness_hw=15" in entry
        and "previous_brightness_hw=15" in entry
        and "avg_rgb=(0,255,0)" in entry
        for entry in logged
    )


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
        _reactive_uniform_hw_streak=6,
        _last_rendered_brightness=15,
        _last_hw_mode_brightness=15,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    # Pulse-time lift still occurs on uniform backends, but it now ramps through
    # the brightness stability guard instead of jumping to max in one frame.
    assert ("set_color", 23) in kb.calls
    assert ("set_brightness", 23) in kb.calls


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


def test_per_key_restore_transition_scales_frame_between_hw_steps(monkeypatch) -> None:
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
        _reactive_active_pulse_mix=0.0,
        _reactive_transition_from_brightness=1,
        _reactive_transition_to_brightness=5,
        _reactive_transition_started_at=100.0,
        _reactive_transition_duration_s=1.0,
        _last_rendered_brightness=1,
        _last_hw_mode_brightness=1,
    )

    monkeypatch.setattr("src.core.effects.reactive._render_brightness.time.monotonic", lambda: 100.35)

    render(engine, color_map={(0, 0): (100, 50, 25)})

    assert ("set_key_colors", 3) in kb.calls
    assert kb.frames[-1][(0, 0)] == (80, 40, 20)
