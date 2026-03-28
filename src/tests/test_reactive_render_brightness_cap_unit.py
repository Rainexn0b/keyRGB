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
    """After a stop/restart (_last_rendered_brightness=None), the stability
    guard should treat None as 0 and ramp up naturally, not jump to full
    brightness on the first frame.  This prevents a full-brightness red flash
    on wake-from-dim when brightness_override=1 is overridden by
    max(engine.brightness, per_key_brightness, reactive_brightness)."""
    from src.core.effects.reactive.render import _MAX_BRIGHTNESS_STEP_PER_FRAME, render

    kb = _DummyKB()

    # Simulate post-stop state: brightness_override=1 set, but per_key and
    # reactive are both 25 (their normal values).  Without the fix,
    # max(1, 25, 25) = 25 and _last_rendered_brightness=None would skip the
    # guard entirely, writing at 25 on the first frame.
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=1,
        reactive_brightness=25,
        per_key_colors={(0, 0): (255, 255, 255)},
        per_key_brightness=25,
        _hw_brightness_cap=None,
        _dim_temp_active=False,
        _last_rendered_brightness=None,  # as reset by engine.stop()
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    written = [b for (op, b) in kb.calls if op == "set_key_colors"]
    assert written, "expected at least one set_key_colors call"
    first_brightness = written[0]
    # First frame should be clamped to _MAX_BRIGHTNESS_STEP_PER_FRAME (8)
    # from 0, not 25.
    assert first_brightness <= _MAX_BRIGHTNESS_STEP_PER_FRAME, (
        f"Expected first frame brightness ≤ {_MAX_BRIGHTNESS_STEP_PER_FRAME} "
        f"to enforce wake-ramp, got {first_brightness}"
    )


def test_engine_stop_resets_last_rendered_brightness() -> None:
    """engine.stop() must reset _last_rendered_brightness to None so that the
    reactive render's stability guard ramps up from 0 on the next start."""
    from src.core.effects.engine_core import _EngineCore

    engine = _EngineCore()
    engine._last_rendered_brightness = 25  # simulate running state
    engine._last_hw_mode_brightness = 25
    engine.stop()

    assert engine._last_rendered_brightness is None, (
        "stop() must reset _last_rendered_brightness to None; "
        "a stale value bypasses the wake-ramp stability guard"
    )
    assert engine._last_hw_mode_brightness is None, (
        "stop() must reset _last_hw_mode_brightness to None; "
        "a stale value causes set_brightness instead of enable_user_mode on first frame"
    )


def test_render_uses_set_brightness_after_first_frame() -> None:
    """After the first frame (enable_user_mode), subsequent brightness changes
    should use set_brightness (lightweight) not enable_user_mode (full reinit)."""
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
        _last_hw_mode_brightness=8,  # already initialized
    )

    # Render at same brightness — should skip enable_user_mode AND set_brightness
    render(engine, color_map={(0, 0): (255, 255, 255)})
    enable_calls = [c for c in kb.calls if c[0] == "enable_user_mode"]
    set_br_calls = [c for c in kb.calls if c[0] == "set_brightness"]
    assert len(enable_calls) == 0, "should not call enable_user_mode when brightness unchanged"
    assert len(set_br_calls) == 0, "should not call set_brightness when brightness unchanged"

    # Now change brightness — should use set_brightness, not enable_user_mode
    kb.calls.clear()
    engine.brightness = 16
    engine.reactive_brightness = 16
    engine.per_key_brightness = 16
    engine._last_rendered_brightness = 8
    render(engine, color_map={(0, 0): (255, 255, 255)})
    enable_calls = [c for c in kb.calls if c[0] == "enable_user_mode"]
    set_br_calls = [c for c in kb.calls if c[0] == "set_brightness"]
    assert len(enable_calls) == 0, "should use set_brightness, not enable_user_mode for brightness change"
    assert len(set_br_calls) == 1, "should call set_brightness once for brightness change"


def test_render_uses_enable_user_mode_on_first_frame() -> None:
    """First frame after stop (mode cache None) must use enable_user_mode."""
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
        _last_hw_mode_brightness=None,  # post-stop
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})
    enable_calls = [c for c in kb.calls if c[0] == "enable_user_mode"]
    assert len(enable_calls) == 1, "first frame after stop must use enable_user_mode"


def test_render_set_brightness_always_after_data_when_dimming() -> None:
    """The ITE 8291 firmware treats SET_BRIGHTNESS as the per-frame commit/
    refresh signal.  Sending it before row data updates the internal register
    but does NOT visually apply until the next commit, so the display stays at
    the old brightness even though get_brightness() returns the new value.
    SET_BRIGHTNESS must therefore always be sent AFTER row data — even when
    dimming — so the new brightness and new frame contents commit together."""
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
        _last_hw_mode_brightness=50,  # hardware was at 50 (dimming step)
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    ops = [op for (op, _) in kb.calls]
    assert "set_brightness" in ops, "set_brightness must be sent"
    assert "set_key_colors" in ops, "set_key_colors must be sent"
    kc_idx = ops.index("set_key_colors")
    br_idx = ops.index("set_brightness")
    assert kc_idx < br_idx, (
        "SET_BRIGHTNESS must always come after set_key_colors (including when "
        f"dimming) so the ITE firmware commits both together; "
        f"got set_key_colors at position {kc_idx}, set_brightness at {br_idx}"
    )


def test_render_set_brightness_after_data_when_brightening() -> None:
    """When brightness increases (brightening), set_key_colors must fire BEFORE
    SET_BRIGHTNESS so new colors are loaded before brightness rises."""
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
        _last_hw_mode_brightness=8,  # hardware was at 8 (lower)
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    ops = [op for (op, _) in kb.calls]
    assert "set_brightness" in ops, "set_brightness must be sent"
    assert "set_key_colors" in ops, "set_key_colors must be sent"
    kc_idx = ops.index("set_key_colors")
    br_idx = ops.index("set_brightness")
    assert kc_idx < br_idx, (
        "When brightening, set_key_colors must fire before set_brightness "
        f"(got set_key_colors at position {kc_idx}, set_brightness at {br_idx})"
    )


def test_render_guard_bypassed_for_dim_temp_downward_jump() -> None:
    """When dim_temp_active=True and brightness is falling, the stability guard
    must be bypassed so the render jumps directly to the dim target in one frame
    instead of stepping down at 8 units/frame.

    The guard's slow ramp (6 frames × 34 ms each ≈ 200 ms) creates 6 separate
    34 ms windows where the new frame is visible at the old higher brightness
    before SET_BRIGHTNESS fires — perceived as a staircase flash on dim.
    Bypassing the guard means only ONE such window (the first frame), which is
    much less perceptible."""
    from src.core.effects.reactive.render import render

    kb = _DummyKB()

    # Simulate steady state at brightness=50, then dim_to_temp fires targeting 5.
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=5,           # engine state after dim_to_temp
        reactive_brightness=50, # reactive_brightness unchanged (high)
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,  # reactive dim no longer sets cap (transition + dim_temp_active suffice)
        _dim_temp_active=True,  # flag set by dim_to_temp
        _last_rendered_brightness=50,   # previous HW brightness
        _last_hw_mode_brightness=50,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    # With the guard bypassed, the first dim frame should jump straight to 5.
    written = [b for (op, b) in kb.calls if op == "set_brightness"]
    assert written, "expected a set_brightness call on first dim frame"
    assert written[0] == 5, (
        f"First dim frame should jump to dim target (5) bypassing the guard, "
        f"got {written[0]}"
    )


def test_render_guard_still_active_for_upward_jumps_under_dim_temp() -> None:
    """The guard bypass only applies to downward brightness jumps during
    dim_temp_active.  Upward jumps (which should not happen during dim, but
    could in theory from a racing writer) should still be clamped."""
    from src.core.effects.reactive.render import _MAX_BRIGHTNESS_STEP_PER_FRAME, render

    kb = _DummyKB()

    # Artificially: dim_temp_active=True but target > prev (shouldn't happen in
    # practice but guard should still protect against it).
    engine = SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=50,
        reactive_brightness=50,
        per_key_colors=None,
        per_key_brightness=0,
        _hw_brightness_cap=None,
        _dim_temp_active=True,
        _last_rendered_brightness=5,    # previous HW was 5
        _last_hw_mode_brightness=5,
    )

    render(engine, color_map={(0, 0): (255, 255, 255)})

    written = [b for (op, b) in kb.calls if op == "set_brightness"]
    assert written, "expected a set_brightness call"
    # Guard should clamp upward jump to at most _MAX_BRIGHTNESS_STEP_PER_FRAME above prev.
    assert written[0] <= 5 + _MAX_BRIGHTNESS_STEP_PER_FRAME, (
        f"Upward jump under dim_temp should still be guarded; "
        f"expected ≤ {5 + _MAX_BRIGHTNESS_STEP_PER_FRAME}, got {written[0]}"
    )


def test_per_key_reactive_pulse_keeps_hw_at_profile_brightness() -> None:
    """Per-key reactive pulses must not trigger a whole-keyboard brightness lift.

    This is the regression that caused the user-visible keyboard-wide shimmer on
    every keypress: the pulse itself was local, but the render path also sent a
    global SET_BRIGHTNESS lift for the entire deck.
    """
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

    # The pulse is visible through the per-key color map, not via a global
    # hardware brightness lift.
    assert ("set_key_colors", 15) in kb.calls
    assert not [c for c in kb.calls if c[0] == "set_brightness"], (
        "per-key reactive frames should not emit SET_BRIGHTNESS when the "
        "profile brightness is unchanged"
    )


def test_per_key_reactive_pulse_first_frame_initializes_mode_at_profile_brightness() -> None:
    """Even on the first frame, per-key reactive pulses should initialize user
    mode at the profile brightness rather than at the pulse target.

    That preserves the no-whole-keyboard-flicker invariant across restarts and
    reactive effect changes, not just during steady-state typing.
    """
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
    assert not [c for c in kb.calls if c[0] == "set_brightness"], (
        "first-frame per-key reactive rendering should initialize at the "
        "profile brightness and avoid a pulse-time hardware lift"
    )


def test_uniform_reactive_pulse_can_still_lift_hw_brightness() -> None:
    """Uniform-only backends keep the legacy fallback: without per-key output,
    a pulse may lift global brightness so reactive typing remains visible.
    """
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

    # Uniform hardware has no per-key map to carry the pulse, so the fallback
    # still lifts hardware brightness for the duration of the pulse.
    assert ("set_color", 50) in kb.calls
    assert ("set_brightness", 50) in kb.calls


def test_uniform_reactive_pulse_returns_directly_to_idle_brightness() -> None:
    """Uniform-only backends should still drop straight back to the idle
    profile brightness once the pulse is gone.

    This preserves the earlier tail-flicker fix while keeping the backend split
    explicit in the tests.
    """
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


def test_per_key_reactive_pulse_respects_dim_temp_lock() -> None:
    """Temp-dim remains authoritative even while a reactive pulse is active.

    This test complements the manual validation log by proving that the newer
    per-key no-lift rule does not weaken the dim-time brightness lock.
    """
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
    assert not [c for c in kb.calls if c == ("set_brightness", 50)], (
        "temp-dim must remain the authoritative hardware brightness cap even "
        "when a pulse is active"
    )
