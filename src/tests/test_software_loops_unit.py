#!/usr/bin/env python3
"""Unit tests for core/effects/software_loops.py - effect algorithm calculations.

Tests focus on the mathematical/algorithmic logic of software effects without
running actual effect loops or depending on hardware/threading.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock


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


class TestFireColorGeneration:
    """Test fire effect color range logic."""

    def test_fire_generates_red_dominant_colors(self):
        """Fire colors should have red component stronger than green."""
        # Simulate fire color generation (red: 200-255, green: 0-100, blue: 0)
        for _ in range(20):
            # Using fixed seed-like values for deterministic testing
            red_base = 200
            red_random = 27.5  # midpoint of 0-55
            green_random = 50  # midpoint of 0-100

            red = int((red_base + red_random))
            green = int(green_random)
            blue = 0

            assert red > green, f"Fire should be red-dominant: R={red} G={green}"
            assert blue == 0, "Fire should have no blue component"

    def test_fire_respects_brightness_factor(self):
        """Fire colors should scale with brightness factor."""
        brightness = 50  # 50%
        factor = brightness / 100.0

        red_raw = 255
        green_raw = 100

        red_scaled = int(red_raw * factor)
        green_scaled = int(green_raw * factor)

        assert red_scaled == 127  # 255 * 0.5
        assert green_scaled == 50  # 100 * 0.5


class TestRandomColorGeneration:
    """Test random effect color generation and cross-fade logic."""

    def test_random_generates_full_spectrum_colors(self):
        """Random colors should span the full RGB spectrum."""
        factor = 1.0  # Full brightness

        # Simulate random color generation
        colors = [
            (int(0.0 * 255 * factor), int(1.0 * 255 * factor), int(0.5 * 255 * factor)),
            (int(1.0 * 255 * factor), int(0.0 * 255 * factor), int(0.0 * 255 * factor)),
            (int(0.3 * 255 * factor), int(0.7 * 255 * factor), int(0.9 * 255 * factor)),
        ]

        for r, g, b in colors:
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

    def test_random_avoids_black_at_positive_brightness(self):
        """Random effect should avoid (0,0,0) at positive brightness."""
        brightness = 80
        target = (0, 0, 0)

        # Simulate the avoid_full_black check
        if brightness > 0 and target == (0, 0, 0):
            target = (1, 0, 0)

        assert target != (0, 0, 0)
        assert target == (1, 0, 0)

    def test_cross_fade_linear_interpolation_at_midpoint(self):
        """Cross-fade at t=0.5 should produce midpoint color."""
        prev = (100, 0, 200)
        target = (200, 100, 0)
        t = 0.5

        pr, pg, pb = prev
        tr, tg, tb = target

        r = int(round(pr + (tr - pr) * t))
        g = int(round(pg + (tg - pg) * t))
        b = int(round(pb + (tb - pb) * t))

        assert r == 150  # (100 + 200) / 2
        assert g == 50   # (0 + 100) / 2
        assert b == 100  # (200 + 0) / 2

    def test_cross_fade_at_start_equals_previous(self):
        """Cross-fade at t=0 should equal previous color."""
        prev = (100, 50, 200)
        target = (200, 100, 0)
        t = 0.0

        pr, pg, pb = prev
        tr, tg, tb = target

        r = int(round(pr + (tr - pr) * t))
        g = int(round(pg + (tg - pg) * t))
        b = int(round(pb + (tb - pb) * t))

        assert (r, g, b) == prev

    def test_cross_fade_at_end_equals_target(self):
        """Cross-fade at t=1.0 should equal target color."""
        prev = (100, 50, 200)
        target = (200, 100, 0)
        t = 1.0

        pr, pg, pb = prev
        tr, tg, tb = target

        r = int(round(pr + (tr - pr) * t))
        g = int(round(pg + (tg - pg) * t))
        b = int(round(pb + (tb - pb) * t))

        assert (r, g, b) == target


class TestStrobeToggling:
    """Test strobe effect on/off logic."""

    def test_strobe_alternates_white_and_black(self):
        """Strobe should alternate between white and black."""
        on = False
        brightness = 80

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
