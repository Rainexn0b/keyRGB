#!/usr/bin/env python3
"""Unit tests for reactive effect helper math.

These tests avoid running the infinite reactive loops; they validate that the
core computations produce non-trivial overlays.
"""

from __future__ import annotations

import logging


class TestRippleWeight:
    def test_weight_is_zero_far_from_ring(self):
        from src.core.effects.reactive.effects import _ripple_weight

        w = _ripple_weight(d=10, radius=2.0, intensity=1.0, band=1.35)
        assert w == 0.0

    def test_weight_is_positive_on_ring(self):
        from src.core.effects.reactive.effects import _ripple_weight

        w = _ripple_weight(d=3, radius=3.0, intensity=0.8, band=1.35)
        assert w > 0.0


class TestRippleRadius:
    def test_radius_interpolates(self):
        from src.core.effects.reactive.effects import _ripple_radius

        assert _ripple_radius(age_s=0.0, ttl_s=1.0, min_radius=0.0, max_radius=8.0) == 0.0
        assert _ripple_radius(age_s=1.0, ttl_s=1.0, min_radius=0.0, max_radius=8.0) == 8.0
        mid = _ripple_radius(age_s=0.5, ttl_s=1.0, min_radius=0.0, max_radius=8.0)
        assert 3.9 < mid < 4.1


def test_set_reactive_active_pulse_mix_logs_traceback_when_cache_write_fails(caplog) -> None:
    from src.core.effects.reactive import effects

    class _BrokenEngine:
        def __init__(self) -> None:
            object.__setattr__(self, "_reactive_active_pulse_mix", 0.25)

        def __setattr__(self, name: str, value) -> None:
            if name == "_reactive_active_pulse_mix":
                raise AttributeError("cache write failed - attribute is read-only")
            object.__setattr__(self, name, value)

    engine = _BrokenEngine()

    with caplog.at_level(logging.ERROR, logger="src.core.effects.reactive.effects"):
        effects._set_reactive_active_pulse_mix(engine, target=1.0)

    assert engine._reactive_active_pulse_mix == 0.25

    records = [record for record in caplog.records if "Failed to cache reactive pulse mix" in record.getMessage()]
    assert records
    assert records[-1].exc_info is not None


def test_set_reactive_active_pulse_mix_ramps_up_instead_of_single_frame_jump() -> None:
    from src.core.effects.reactive import effects

    class _Engine:
        _reactive_active_pulse_mix = 0.0

    engine = _Engine()

    effects._set_reactive_active_pulse_mix(engine, target=1.0)
    assert 0.40 <= float(engine._reactive_active_pulse_mix) <= 0.50

    effects._set_reactive_active_pulse_mix(engine, target=1.0)
    assert 0.85 <= float(engine._reactive_active_pulse_mix) <= 0.95

    effects._set_reactive_active_pulse_mix(engine, target=1.0)
    assert float(engine._reactive_active_pulse_mix) == 1.0


def test_set_reactive_active_pulse_mix_preserves_tail_decay_on_drop_to_zero() -> None:
    from src.core.effects.reactive import effects

    class _Engine:
        _reactive_active_pulse_mix = 1.0

    engine = _Engine()
    effects._set_reactive_active_pulse_mix(engine, target=0.0)

    assert 0.60 <= float(engine._reactive_active_pulse_mix) <= 0.70


def test_fade_loop_per_key_backdrop_applies_pulse_scale_to_mix_weight() -> None:
    """Fade loop per-key backdrop path: pulse_scale controls mix weight so the reactive
    brightness slider remains effective even when the boost color is black or white."""
    from src.core.effects.reactive._ripple_helpers import build_ripple_color_map_into
    from src.core.effects.reactive._ripple_helpers import mix, scale

    # All-white backdrop: contrasting highlight is black; scale(black, x) == black.
    # Mix-weight path must still produce a visible gradient.
    base_white = {(0, 0): (255, 255, 255)}
    overlay_full = {(0, 0): (1.0, 0.0)}

    result_low = build_ripple_color_map_into(
        {},
        base=base_white,
        base_unscaled=base_white,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=0.1,
    )
    result_high = build_ripple_color_map_into(
        {},
        base=base_white,
        base_unscaled=base_white,
        overlay=overlay_full,
        per_key_backdrop_active=True,
        manual=None,
        pulse_scale=1.0,
    )

    # Different scales must produce visually different results
    assert result_low[(0, 0)] != result_high[(0, 0)]


def test_global_hue_formula_is_fixed_rate_not_pace_coupled() -> None:
    """global_hue advance should be 2.0 deg/frame regardless of p.
    Verify the formula (global_hue + 2.0) % 360.0 matches expectations
    and that multiplying by p is NOT present in the ripple loop source."""
    import ast
    import inspect
    from src.core.effects.reactive import _ripple_loop

    source = inspect.getsource(_ripple_loop.run_reactive_ripple_loop)
    tree = ast.parse(source)

    # Find all BinOp nodes that are (global_hue + ...) or (... + 2.0 * p)
    pace_coupled = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "global_hue":
                    # The RHS should not contain a multiplication involving p
                    rhs_src = ast.unparse(node.value)
                    if "* p" in rhs_src or "p *" in rhs_src:
                        pace_coupled = True

    assert not pace_coupled, "global_hue advance must not be multiplied by p (pace-coupled)"
