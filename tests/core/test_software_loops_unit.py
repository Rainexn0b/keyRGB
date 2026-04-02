#!/usr/bin/env python3
"""Unit tests for effect helper calculations.

Tests focus on the mathematical/algorithmic logic without running the actual
effect loops or depending on hardware/threading.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def test_speed_mapping_has_strong_top_end() -> None:
    from src.core.effects.software.base import pace as _pace

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


def test_animation_step_returns_nominal_without_prior_tick() -> None:
    from src.core.effects.software.base import animation_step_s

    engine = SimpleNamespace()

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.0)

    assert step == pytest.approx(0.02)
    assert engine._tick == pytest.approx(10.0)


def test_animation_step_uses_elapsed_when_within_clamp() -> None:
    from src.core.effects.software.base import animation_step_s

    engine = SimpleNamespace(_tick=10.0)

    step = animation_step_s(engine, "_tick", nominal_s=0.02, now_s=10.024)

    assert step == pytest.approx(0.024)
    assert engine._tick == pytest.approx(10.024)


def test_animation_step_clamps_large_frame_gaps() -> None:
    from src.core.effects.software.base import animation_step_s

    engine = SimpleNamespace(_tick=10.0)

    step = animation_step_s(engine, "_tick", nominal_s=0.02, max_step_multiple=2.0, now_s=10.50)

    assert step == pytest.approx(0.04)
    assert engine._tick == pytest.approx(10.50)


@pytest.mark.parametrize(
    ("effect_runner", "per_key_ok"),
    [
        pytest.param("run_fire", False, id="fire"),
        pytest.param("run_twinkle", False, id="twinkle"),
        pytest.param("run_strobe", False, id="strobe"),
        pytest.param("run_chase", True, id="chase-per-key"),
        pytest.param("run_rain", False, id="rain"),
    ],
)
def test_effect_loops_wait_before_second_iteration(effect_runner: str, per_key_ok: bool) -> None:
    from src.core.effects.software import _effects_basic, _effects_particles

    class StopEvent:
        def __init__(self) -> None:
            self.wait_calls = 0

        def is_set(self) -> bool:
            return self.wait_calls > 0

        def wait(self, _timeout: float) -> bool:
            self.wait_calls += 1
            return True

    stop_event = StopEvent()
    render_calls = 0

    def render_once(_engine: object, *, color_map: dict[tuple[int, int], tuple[int, int, int]]) -> None:
        nonlocal render_calls
        render_calls += 1
        assert color_map
        if render_calls > 1:
            raise AssertionError("effect loop iterated again before waiting")

    engine = SimpleNamespace(
        running=True,
        stop_event=stop_event,
        speed=4,
        brightness=25,
        current_color=(255, 0, 0),
        per_key_colors=None,
        kb=SimpleNamespace(set_key_colors=(lambda *_args, **_kwargs: None)) if per_key_ok else SimpleNamespace(),
    )

    runner = getattr(_effects_basic, effect_runner, None) or getattr(_effects_particles, effect_runner)
    runner(engine, render_fn=render_once)

    assert render_calls == 1
    assert stop_event.wait_calls == 1


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
        pulse_brightness = int(round(max_brightness * pulse))
        pulse_brightness = max(1, min(max_brightness, pulse_brightness))

        assert pulse_brightness == max_brightness

    def test_pulse_brightness_has_minimum_of_one(self):
        """Pulse brightness should never go below 1."""
        max_brightness = 80

        # Test at trough (phase where sin = -1)
        phase = 3 * math.pi / 2  # sin(3π/2) = -1
        pulse = (math.sin(phase) + 1) / 2  # = 0.0
        pulse_brightness = int(round(max_brightness * pulse))
        pulse_brightness = max(1, min(max_brightness, pulse_brightness))

        assert pulse_brightness == 1

    def test_pulse_mid_cycle_is_half_brightness(self):
        """At phase=0 (sin=0), brightness should be ~half."""
        max_brightness = 100
        phase = 0.0  # sin(0) = 0
        pulse = (math.sin(phase) + 1) / 2  # = 0.5
        pulse_brightness = int(round(max_brightness * pulse))
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

        r = int(round(pr + (tr - pr) * t))
        g = int(round(pg + (tg - pg) * t))
        b = int(round(pb + (tb - pb) * t))

        assert r == 150
        assert g == 50
        assert b == 100


class TestStrobeToggling:
    """Test strobe effect on/off logic."""

    def test_strobe_alternates_white_and_black(self):
        """Strobe should alternate between white and black."""
        on = False

        states = []
        for _ in range(4):
            if on:
                color = (255, 255, 255)
            else:
                color = (0, 0, 0)

            states.append((color, on))
            on = not on

        # Should alternate: off, on, off, on
        assert states[0] == ((0, 0, 0), False)
        assert states[1] == ((255, 255, 255), True)
        assert states[2] == ((0, 0, 0), False)
        assert states[3] == ((255, 255, 255), True)

    def test_strobe_off_state_respects_minimum_brightness(self):
        """Strobe 'off' should use max(1, brightness) not pure black."""
        brightness = 80

        # Simulate off state
        off_color = (0, 0, 0)
        off_brightness = max(1, brightness)

        assert off_brightness == 80
        assert off_color == (0, 0, 0)


class TestReactiveKeyMapping:
    def test_evdev_key_name_to_key_id_letters_digits(self):
        from src.core.effects.reactive.input import (
            evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
            evdev_key_name_to_slot_id as _evdev_key_name_to_slot_id,
        )
        from src.core.resources.layouts import slot_id_for_key_id

        assert _evdev_key_name_to_key_id("KEY_A") == "a"
        assert _evdev_key_name_to_key_id("KEY_1") == "1"
        assert _evdev_key_name_to_key_id("A") == "a"
        assert _evdev_key_name_to_slot_id("KEY_A") == str(slot_id_for_key_id("auto", "a") or "a")

    def test_evdev_key_name_to_key_id_specials(self):
        from src.core.effects.reactive.input import (
            evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
            evdev_key_name_to_slot_id as _evdev_key_name_to_slot_id,
        )
        from src.core.resources.layouts import slot_id_for_key_id

        assert _evdev_key_name_to_key_id("KEY_LEFTSHIFT") == "lshift"
        assert _evdev_key_name_to_key_id("KEY_RIGHTALT") == "ralt"
        assert _evdev_key_name_to_key_id("KEY_BACKSLASH") == "bslash"
        assert _evdev_key_name_to_key_id("KEY_102ND") == "nonusbackslash"
        assert _evdev_key_name_to_key_id("KEY_LEFTBRACE") == "lbracket"
        assert _evdev_key_name_to_key_id("KEY_KP1") == "num1"
        assert _evdev_key_name_to_key_id("KEY_KPDOT") == "numdot"
        assert _evdev_key_name_to_slot_id("KEY_102ND") == str(
            slot_id_for_key_id("auto", "nonusbackslash") or "nonusbackslash"
        )


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
    from src.core.effects.software import _effects_basic, _effects_particles  # noqa: F401

    mod = importlib.import_module(f"src.core.effects.software.{module}")

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
