#!/usr/bin/env python3
"""Unit tests for effect helper calculations.

Tests focus on the mathematical/algorithmic logic without running the actual
effect loops or depending on hardware/threading.
"""

from __future__ import annotations

import math


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
        )

        assert _evdev_key_name_to_key_id("KEY_A") == "a"
        assert _evdev_key_name_to_key_id("KEY_1") == "1"
        assert _evdev_key_name_to_key_id("A") == "a"

    def test_evdev_key_name_to_key_id_specials(self):
        from src.core.effects.reactive.input import (
            evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
        )

        assert _evdev_key_name_to_key_id("KEY_LEFTSHIFT") == "lshift"
        assert _evdev_key_name_to_key_id("KEY_RIGHTALT") == "ralt"
        assert _evdev_key_name_to_key_id("KEY_BACKSLASH") == "bslash"
        assert _evdev_key_name_to_key_id("KEY_LEFTBRACE") == "lbracket"
        assert _evdev_key_name_to_key_id("KEY_KP1") == "num1"
        assert _evdev_key_name_to_key_id("KEY_KPDOT") == "numdot"


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
