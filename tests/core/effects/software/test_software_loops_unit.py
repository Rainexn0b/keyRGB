#!/usr/bin/env python3
"""Unit tests for rainbow/wave/breathing loops and shared effect math.

Tests focus on the mathematical/algorithmic logic without running the actual
effect loops or depending on hardware/threading.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def test_software_clamp_preserves_nan_instead_of_promoting_to_full_scale() -> None:
    from keyrgb.core.effects.software.base import clamp01

    assert math.isnan(clamp01(float("nan")))


def test_speed_mapping_has_strong_top_end() -> None:
    from keyrgb.core.effects.software.base import pace as _pace

    class E:
        def __init__(self, speed: int):
            self.speed = speed

    p0 = _pace(E(0))
    p5 = _pace(E(5))
    p10 = _pace(E(10))

    assert p0 > 0.0
    assert p10 > p5
    # The top end should be meaningfully faster.
    assert p10 >= (p5 * 2.5)


def test_speed_mapping_preserves_none_and_invalid_fallbacks() -> None:
    from keyrgb.core.effects.software.base import pace as _pace

    assert _pace(SimpleNamespace(speed=None)) == pytest.approx(_pace(SimpleNamespace(speed=0)))
    assert _pace(SimpleNamespace(speed="fast")) == pytest.approx(_pace(SimpleNamespace(speed=4)))
    assert _pace(SimpleNamespace()) == pytest.approx(_pace(SimpleNamespace(speed=4)))


def test_animation_step_returns_nominal_without_prior_tick() -> None:
    from keyrgb.core.effects.software.base import animation_step_s

    engine = SimpleNamespace()

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.0)

    assert step == pytest.approx(0.02)
    assert engine._tick == pytest.approx(10.0)


def test_animation_step_uses_elapsed_when_within_clamp() -> None:
    from keyrgb.core.effects.software.base import animation_step_s

    engine = SimpleNamespace(_tick=10.0)

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.024)

    assert step == pytest.approx(0.024)
    assert engine._tick == pytest.approx(10.024)


def test_animation_step_clamps_large_frame_gaps() -> None:
    from keyrgb.core.effects.software.base import animation_step_s

    engine = SimpleNamespace(_tick=10.0)

    step = animation_step_s(engine, "_tick", nominal_s=0.02, max_step_multiple=2.0, now_s=10.50)

    assert step == pytest.approx(0.04)
    assert engine._tick == pytest.approx(10.50)


def test_animation_step_ignores_uncoercible_prior_tick() -> None:
    from keyrgb.core.effects.software.base import animation_step_s

    engine = SimpleNamespace(_tick=object())

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.0)

    assert step == pytest.approx(0.02)
    assert engine._tick == pytest.approx(10.0)


class _ReadOnlyTickEngine:
    def __init__(self, tick: float) -> None:
        self._stored_tick = tick

    @property
    def _tick(self) -> float:
        return self._stored_tick


def test_animation_step_tolerates_read_only_tick_attr() -> None:
    from keyrgb.core.effects.software.base import animation_step_s

    engine = _ReadOnlyTickEngine(10.0)

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.02)

    assert step == pytest.approx(0.02)
    assert engine._tick == pytest.approx(10.0)


class TestPulseCalculation:
    """Test pulse effect sine wave brightness calculation."""

    def test_sine_wave_produces_zero_to_one_range(self):
        """Pulse calculation should produce values between 0 and 1."""
        phases = [0.0, 0.5, 1.0, 1.5, 2.0, 3.14, 6.28]

        for phase in phases:
            pulse = (math.sin(phase) + 1) / 2
            assert 0.0 <= pulse <= 1.0, f"pulse={pulse} at phase={phase}"

    def test_pulse_brightness_clamped_to_max_brightness(self):
        """Pulse brightness should never exceed max brightness."""
        max_brightness = 80

        # Test at peak (phase where sin = 1)
        phase = math.pi / 2  # sin(π/2) = 1
        pulse = (math.sin(phase) + 1) / 2  # = 1.0
        pulse_brightness = round(max_brightness * pulse)
        pulse_brightness = max(1, min(max_brightness, pulse_brightness))

        assert pulse_brightness == max_brightness

    def test_pulse_brightness_has_minimum_of_one(self):
        """Pulse brightness should never go below 1."""
        max_brightness = 80

        # Test at trough (phase where sin = -1)
        phase = 3 * math.pi / 2  # sin(3π/2) = -1
        pulse = (math.sin(phase) + 1) / 2  # = 0.0
        pulse_brightness = round(max_brightness * pulse)
        pulse_brightness = max(1, min(max_brightness, pulse_brightness))

        assert pulse_brightness == 1

    def test_pulse_mid_cycle_is_half_brightness(self):
        """At phase=0 (sin=0), brightness should be ~half."""
        max_brightness = 100
        phase = 0.0  # sin(0) = 0
        pulse = (math.sin(phase) + 1) / 2  # = 0.5
        pulse_brightness = round(max_brightness * pulse)
        pulse_brightness = max(1, min(max_brightness, pulse_brightness))

        assert 45 <= pulse_brightness <= 55  # ~50 with rounding tolerance


class TestCrossFadeMath:
    """Basic lerp sanity checks used by multiple effects."""

    def test_cross_fade_linear_interpolation_at_midpoint(self):
        prev = (100, 0, 200)
        target = (200, 100, 0)
        t = 0.5

        pr, pg, pb = prev
        tr, tg, tb = target

        r = round(pr + (tr - pr) * t)
        g = round(pg + (tg - pg) * t)
        b = round(pb + (tb - pb) * t)

        assert r == 150
        assert g == 50
        assert b == 100


class TestBrightnessFactorCalculation:
    """Test brightness factor used by effects."""

    def test_brightness_factor_full_brightness(self):
        """At 100 brightness, factor should be 1.0."""
        brightness = 100
        factor = brightness / 100.0

        assert factor == 1.0

    def test_brightness_factor_half_brightness(self):
        """At 50 brightness, factor should be 0.5."""
        brightness = 50
        factor = brightness / 100.0

        assert factor == 0.5

    def test_brightness_factor_minimum_brightness(self):
        """At 1 brightness, factor should be 0.01."""
        brightness = 1
        factor = brightness / 100.0

        assert factor == 0.01

    def test_color_scaled_by_brightness_factor(self):
        """Colors should scale proportionally with brightness factor."""
        brightness = 60
        factor = brightness / 100.0

        base_color = (200, 150, 100)
        scaled = tuple(int(c * factor) for c in base_color)

        assert scaled == (120, 90, 60)


@pytest.mark.parametrize(
    ("effect_runner", "module"),
    [
        pytest.param("run_rainbow_swirl", "_effects_basic", id="rainbow_swirl"),
        pytest.param("run_rainbow_wave", "_effects_basic", id="rainbow_wave"),
        pytest.param("run_spectrum_cycle", "_effects_basic", id="spectrum_cycle"),
        pytest.param("run_color_cycle", "_effects_basic", id="color_cycle"),
    ],
)
def test_smooth_cycling_effects_use_constant_frame_step(effect_runner: str, module: str) -> None:
    """Regression: rainbow_swirl and similar effects must advance their hue/phase
    by a constant amount each frame, not by wall-clock elapsed time.

    Using elapsed time amplifies USB write-time jitter by the pace multiplier
    (up to ×10 at max speed), causing visible choppy color steps on the hardware.
    Constant step (matching v0.18.1 behaviour) eliminates this jitter.

    This test verifies equal hue/phase advance even when two frames are rendered
    back-to-back with no actual delay between them.
    """
    import importlib

    from keyrgb.core.effects.software import _effects_basic, _effects_particles  # noqa: F401

    mod = importlib.import_module(f"keyrgb.core.effects.software.{module}")

    class StopEvent:
        def __init__(self) -> None:
            self._count = 0

        def is_set(self) -> bool:
            return self._count >= 2

        def wait(self, _timeout: float) -> bool:
            self._count += 1
            return True

    rendered: list[dict] = []

    def capture(_engine: object, *, color_map: dict) -> None:
        rendered.append(dict(color_map))

    engine = SimpleNamespace(
        running=True,
        stop_event=StopEvent(),
        speed=10,  # max speed — worst case for jitter amplification
        brightness=25,
        current_color=(255, 0, 0),
        per_key_colors=None,
        kb=SimpleNamespace(),
    )

    runner = getattr(mod, effect_runner)
    runner(engine, render_fn=capture)

    assert len(rendered) == 2, "expected exactly 2 rendered frames"

    # All keys must have changed by the same delta between frame 1 and frame 2.
    # (For spectrum_cycle and color_cycle all keys are uniform, so we just
    # check that frame 2 differs from frame 1 — both frames advance equally
    # because the hue step is constant.)
    frame0 = rendered[0]
    frame1 = rendered[1]
    # At speed=10 the per-frame delta is non-zero.
    assert frame0 != frame1, "effect did not advance between frames"
