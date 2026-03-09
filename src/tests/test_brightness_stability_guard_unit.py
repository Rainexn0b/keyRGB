"""Tests for the per-frame brightness stability guard in the reactive render path.

The guard (in ``_resolve_brightness()``) clamps frame-to-frame brightness
changes to ``_MAX_BRIGHTNESS_STEP_PER_FRAME`` to prevent single-frame jumps
caused by concurrent brightness writers racing.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _RecordingKB:
    """Minimal keyboard stub that records brightness values from calls."""

    def __init__(self) -> None:
        self.brightness_log: list[int] = []

    def enable_user_mode(self, *, brightness: int, save: bool = False) -> None:
        pass

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False) -> None:
        self.brightness_log.append(int(brightness))

    def set_color(self, _color, *, brightness: int) -> None:
        self.brightness_log.append(int(brightness))


def _mk_engine(
    *,
    brightness: int = 50,
    per_key_brightness: int = 50,
    reactive_brightness: int = 50,
    hw_brightness_cap: Optional[int] = None,
    dim_temp_active: bool = False,
    last_rendered: Optional[int] = None,
    has_per_key: bool = True,
) -> SimpleNamespace:
    kb = _RecordingKB()
    if not has_per_key:
        # Remove set_key_colors so render falls back to uniform
        kb.set_key_colors = None  # type: ignore[assignment]

    return SimpleNamespace(
        kb=kb,
        kb_lock=_DummyLock(),
        brightness=brightness,
        per_key_brightness=per_key_brightness,
        reactive_brightness=reactive_brightness,
        per_key_colors={(0, 0): (255, 0, 0)} if has_per_key else None,
        _hw_brightness_cap=hw_brightness_cap,
        _dim_temp_active=dim_temp_active,
        _last_rendered_brightness=last_rendered,
    )


# ---------------------------------------------------------------------------
# _resolve_brightness tests
# ---------------------------------------------------------------------------


def test_guard_clamps_large_upward_jump() -> None:
    """Brightness jump > _MAX_BRIGHTNESS_STEP_PER_FRAME is clamped."""
    from src.core.effects.reactive.render import _resolve_brightness, _MAX_BRIGHTNESS_STEP_PER_FRAME

    engine = _mk_engine(brightness=50, last_rendered=3)
    _, _, hw = _resolve_brightness(engine)
    assert hw <= 3 + _MAX_BRIGHTNESS_STEP_PER_FRAME


def test_guard_clamps_large_downward_jump() -> None:
    """Brightness drop > _MAX_BRIGHTNESS_STEP_PER_FRAME is clamped."""
    from src.core.effects.reactive.render import _resolve_brightness, _MAX_BRIGHTNESS_STEP_PER_FRAME

    engine = _mk_engine(brightness=3, per_key_brightness=3, reactive_brightness=3, last_rendered=50)
    _, _, hw = _resolve_brightness(engine)
    assert hw >= 50 - _MAX_BRIGHTNESS_STEP_PER_FRAME


def test_guard_allows_small_change() -> None:
    """Changes within _MAX_BRIGHTNESS_STEP_PER_FRAME are not clamped."""
    from src.core.effects.reactive.render import _resolve_brightness

    engine = _mk_engine(brightness=45, last_rendered=50)
    _, _, hw = _resolve_brightness(engine)
    # 50 -> 45 is a delta of 5, which is <= 8 (default step limit)
    assert hw == 50  # max(45, 50, 50) = 50, same as last_rendered


def test_guard_inactive_when_no_previous_frame() -> None:
    """First frame (no _last_rendered_brightness): no clamping applied."""
    from src.core.effects.reactive.render import _resolve_brightness

    engine = _mk_engine(brightness=50, last_rendered=None)
    _, _, hw = _resolve_brightness(engine)
    assert hw == 50


def test_guard_converges_over_multiple_frames() -> None:
    """Repeated frames should ramp brightness toward the target."""
    from src.core.effects.reactive.render import _resolve_brightness, _MAX_BRIGHTNESS_STEP_PER_FRAME

    engine = _mk_engine(brightness=50, last_rendered=3)
    frames = []
    for _ in range(20):
        _, _, hw = _resolve_brightness(engine)
        frames.append(hw)
        engine._last_rendered_brightness = hw

    # Should have ramped up toward 50
    assert frames[-1] == 50
    # Each frame-to-frame delta should be <= _MAX_BRIGHTNESS_STEP_PER_FRAME
    for i in range(1, len(frames)):
        assert abs(frames[i] - frames[i - 1]) <= _MAX_BRIGHTNESS_STEP_PER_FRAME


def test_guard_works_with_dim_temp_cap() -> None:
    """Guard still respects policy cap during ramp."""
    from src.core.effects.reactive.render import _resolve_brightness

    engine = _mk_engine(
        brightness=3,
        per_key_brightness=3,
        reactive_brightness=50,
        hw_brightness_cap=3,
        dim_temp_active=True,
        last_rendered=50,
    )
    frames = []
    for _ in range(20):
        _, _, hw = _resolve_brightness(engine)
        frames.append(hw)
        engine._last_rendered_brightness = hw

    # Should converge to 3 (the cap)
    assert frames[-1] == 3
    # Should never exceed cap
    assert all(f <= 50 for f in frames)


# ---------------------------------------------------------------------------
# render() integration tests — _last_rendered_brightness tracking
# ---------------------------------------------------------------------------


def test_render_updates_last_rendered_brightness() -> None:
    """render() should update engine._last_rendered_brightness after each frame."""
    from src.core.effects.reactive.render import render

    engine = _mk_engine(brightness=25, last_rendered=None)
    color_map = {(0, 0): (255, 255, 255)}

    render(engine, color_map=color_map)
    assert engine._last_rendered_brightness is not None
    assert engine._last_rendered_brightness == 50  # max(25, 50, 50) = 50


def test_render_ramps_brightness_over_multiple_frames() -> None:
    """Simulated dim → restore: brightness should ramp smoothly, not jump."""
    from src.core.effects.reactive.render import render, _MAX_BRIGHTNESS_STEP_PER_FRAME

    # Start at dim brightness
    engine = _mk_engine(
        brightness=3,
        per_key_brightness=3,
        reactive_brightness=3,
        hw_brightness_cap=3,
        dim_temp_active=True,
        last_rendered=3,
    )
    color_map = {(0, 0): (255, 255, 255)}

    # Render a few frames at dim
    for _ in range(3):
        render(engine, color_map=color_map)

    assert engine._last_rendered_brightness == 3

    # Simulate restore: clear cap, raise brightness instantly
    engine._hw_brightness_cap = None
    engine._dim_temp_active = False
    engine.brightness = 50
    engine.per_key_brightness = 50
    engine.reactive_brightness = 50

    # Render and verify brightness ramps up, not jumps
    brightness_values = []
    for _ in range(20):
        render(engine, color_map=color_map)
        brightness_values.append(engine._last_rendered_brightness)

    # Should converge to 50
    assert brightness_values[-1] == 50

    # Each step should be <= _MAX_BRIGHTNESS_STEP_PER_FRAME from the previous
    prev = 3
    for v in brightness_values:
        assert abs(v - prev) <= _MAX_BRIGHTNESS_STEP_PER_FRAME, (
            f"Jump {prev} -> {v} exceeds max step {_MAX_BRIGHTNESS_STEP_PER_FRAME}"
        )
        prev = v


# ---------------------------------------------------------------------------
# _dim_temp_active propagation to engine
# ---------------------------------------------------------------------------


def test_dim_temp_active_propagated_to_engine_on_dim() -> None:
    """_set_engine_hw_brightness_cap should set _dim_temp_active on the engine."""
    from src.tray.pollers._idle_power_actions import _set_engine_hw_brightness_cap

    engine = SimpleNamespace(_hw_brightness_cap=None, _dim_temp_active=False)

    _set_engine_hw_brightness_cap(engine, 5)
    assert engine._dim_temp_active is True
    assert engine._hw_brightness_cap == 5


def test_dim_temp_active_cleared_on_engine_on_restore() -> None:
    """_set_engine_hw_brightness_cap(None) should clear both cap and flag."""
    from src.tray.pollers._idle_power_actions import _set_engine_hw_brightness_cap

    engine = SimpleNamespace(_hw_brightness_cap=5, _dim_temp_active=True)

    _set_engine_hw_brightness_cap(engine, None)
    assert engine._dim_temp_active is False
    assert engine._hw_brightness_cap is None


def test_engine_init_has_proper_dim_attributes() -> None:
    """EffectsEngine.__init__ should declare _hw_brightness_cap and _dim_temp_active."""
    from src.core.effects.engine import EffectsEngine

    engine = EffectsEngine()
    assert hasattr(engine, "_hw_brightness_cap")
    assert engine._hw_brightness_cap is None
    assert hasattr(engine, "_dim_temp_active")
    assert engine._dim_temp_active is False
    assert hasattr(engine, "_last_rendered_brightness")
    assert engine._last_rendered_brightness is None
