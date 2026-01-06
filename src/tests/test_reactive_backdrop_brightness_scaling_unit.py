from __future__ import annotations


def test_reactive_backdrop_brightness_scaling_keeps_base_dim() -> None:
    from src.core.effects.reactive.render import apply_backdrop_brightness_scale, backdrop_brightness_scale_factor

    class FakeEngine:
        def __init__(self):
            self.per_key_brightness = 5

    engine = FakeEngine()
    # Effect brightness is 50 (100%); base brightness is 5 (10%).
    factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=50)
    assert abs(factor - 0.1) < 1e-9

    base_unscaled = {(0, 0): (200, 100, 50)}
    base_scaled = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
    assert base_scaled[(0, 0)] == (20, 10, 5)


def test_reactive_backdrop_brightness_scaling_noop_without_base_brightness() -> None:
    from src.core.effects.reactive.render import apply_backdrop_brightness_scale, backdrop_brightness_scale_factor

    class FakeEngine:
        def __init__(self):
            self.per_key_brightness = None

    engine = FakeEngine()
    factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=50)
    assert factor == 1.0

    base_unscaled = {(0, 0): (200, 100, 50)}
    base_scaled = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
    assert base_scaled == base_unscaled
