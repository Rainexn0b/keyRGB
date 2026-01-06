from __future__ import annotations

from src.core.effects.reactive.render import (
    apply_backdrop_brightness_scale,
    backdrop_brightness_scale_factor,
    pulse_brightness_scale_factor,
    _resolve_brightness,
)


class FakeEngine:
    def __init__(self, eff=25, base=None, per_key_colors=None):
        self.brightness = eff
        self.per_key_brightness = base
        # Simulate active per-key colors if dict provided
        self.per_key_colors = per_key_colors


def test_resolve_brightness() -> None:
    # Case 1: Dim Profile (Base=5), Bright Effect (Eff=50)
    # Global should be 50.
    engine = FakeEngine(eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)})
    base, eff, glob = _resolve_brightness(engine)
    assert base == 5
    assert eff == 50
    assert glob == 50

    # Case 2: Bright Profile (Base=50), Dim Effect (Eff=5)
    # Global should be 50.
    engine = FakeEngine(eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})
    base, eff, glob = _resolve_brightness(engine)
    assert base == 50
    assert eff == 5
    assert glob == 50

    # Case 3: No backdrop (per_key_colors None)
    # Global should ignore base (base becomes 0).
    engine = FakeEngine(eff=25, base=50, per_key_colors=None)
    base, eff, glob = _resolve_brightness(engine)
    # Base defaults to 0 because per_key_colors is None
    assert base == 0
    assert eff == 25
    assert glob == 25


def test_scaling_factors_dim_base_bright_effect() -> None:
    # Base=5, Eff=50 -> Global=50
    engine = FakeEngine(eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)})

    # Backdrop scale: 5/50 = 0.1
    b_factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=50)
    assert abs(b_factor - 0.1) < 1e-9

    # Pulse scale: 50/50 = 1.0
    p_factor = pulse_brightness_scale_factor(engine)
    assert abs(p_factor - 1.0) < 1e-9


def test_scaling_factors_bright_base_dim_effect() -> None:
    # Base=50, Eff=5 -> Global=50
    engine = FakeEngine(eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})

    # Backdrop scale: 50/50 = 1.0
    b_factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=5)
    assert abs(b_factor - 1.0) < 1e-9

    # Pulse scale: 5/50 = 0.1
    p_factor = pulse_brightness_scale_factor(engine)
    assert abs(p_factor - 0.1) < 1e-9


def test_scaling_application() -> None:
    # Test RGB scaling application
    base_unscaled = {(0, 0): (200, 100, 50)}
    factor = 0.1
    base_scaled = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
    assert base_scaled[(0, 0)] == (20, 10, 5)
