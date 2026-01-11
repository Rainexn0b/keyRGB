from __future__ import annotations

from src.core.effects.reactive.render import (
    apply_backdrop_brightness_scale,
    backdrop_brightness_scale_factor,
    pulse_brightness_scale_factor,
    _resolve_brightness,
)


class FakeEngine:
    def __init__(self, *, global_hw=25, eff=25, base=None, per_key_colors=None):
        # Global hardware brightness cap (profile/policy).
        self.brightness = global_hw
        # Reactive typing pulse/highlight target brightness.
        self.reactive_brightness = eff
        self.per_key_brightness = base
        # Simulate active per-key colors if dict provided
        self.per_key_colors = per_key_colors


def test_resolve_brightness() -> None:
    # Case 1: Dim Profile (Global=5, Base=5), Bright Effect (Eff=50)
    # Global is the profile/policy cap (5).
    engine = FakeEngine(global_hw=5, eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)})
    base, eff, glob = _resolve_brightness(engine)
    assert base == 5
    assert eff == 50
    assert glob == 5

    # Case 2: Bright Profile (Global=50, Base=50), Dim Effect (Eff=5)
    engine = FakeEngine(global_hw=50, eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})
    base, eff, glob = _resolve_brightness(engine)
    assert base == 50
    assert eff == 5
    assert glob == 50

    # Case 3: No backdrop (per_key_colors None)
    # Global should ignore base (base becomes 0).
    engine = FakeEngine(global_hw=25, eff=25, base=50, per_key_colors=None)
    base, eff, glob = _resolve_brightness(engine)
    # Base defaults to 0 because per_key_colors is None
    assert base == 0
    assert eff == 25
    assert glob == 25


def test_scaling_factors_dim_base_bright_effect() -> None:
    # Global=5 caps everything (pulses can't exceed global).
    engine = FakeEngine(global_hw=5, eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)})

    # Backdrop scale: base/global = 5/5 = 1.0
    b_factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=50)
    assert abs(b_factor - 1.0) < 1e-9

    # Pulse scale: eff>=global => 1.0
    p_factor = pulse_brightness_scale_factor(engine)
    assert abs(p_factor - 1.0) < 1e-9


def test_scaling_factors_bright_base_dim_effect() -> None:
    # Base=50, Eff=5, Global=50
    engine = FakeEngine(global_hw=50, eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})

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
