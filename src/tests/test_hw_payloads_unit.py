#!/usr/bin/env python3
"""Unit tests for effects/hw_payloads.py - protocol packet construction logic.

Tests focus on the pure data transformation logic for building hardware effect payloads,
avoiding brittle dependencies on specific hardware or UI elements.
"""

from __future__ import annotations

import logging
from threading import RLock
from unittest.mock import MagicMock

import pytest

from src.core.backends.base import legacy_builder_supported_args, make_hardware_effect_descriptor


def _descriptor(builder, *supported_args: str):
    return make_hardware_effect_descriptor(builder, supported_args=supported_args)


class TestAllowedHwEffectKeys:
    """Test typed hardware effect key exposure and legacy wrapping helpers."""

    def test_legacy_builder_supported_args_extracts_closure_keys(self):
        """Legacy ite8291r3-style builders should still wrap cleanly."""

        def make_effect_func():
            args = {"speed": None, "brightness": None, "color": None}

            def effect_func(**kwargs):
                _ = kwargs
                return args

            return effect_func

        result = legacy_builder_supported_args(make_effect_func())

        assert result == frozenset({"speed", "brightness", "color"})

    def test_legacy_builder_supported_args_returns_empty_when_unreadable(self):
        mock_func = MagicMock()
        del mock_func.__code__

        result = legacy_builder_supported_args(mock_func)
        assert result == frozenset()

    def test_uses_typed_descriptor_supported_args(self):
        """Typed hardware descriptors should expose explicit supported args."""
        from src.core.effects.hw_payloads import allowed_hw_effect_keys

        descriptor = _descriptor(
            lambda **kwargs: kwargs,
            "speed",
            "brightness",
            "direction",
        )

        result = allowed_hw_effect_keys(descriptor, logger=logging.getLogger())

        assert result == {"speed", "brightness", "direction"}


class TestBuildHwEffectPayload:
    """Test build_hw_effect_payload construction logic."""

    def test_inverts_speed_scale_correctly(self):
        """UI speed 10 (fastest) should map to HW speed 1 (fastest)."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        kb_lock = RLock()

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        result = build_hw_effect_payload(
            effect_name="wave",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness"),
            ui_speed=10,  # fastest in UI
            brightness=50,
            current_color=(255, 0, 0),
            hw_colors={"red": 1},
            kb=mock_kb,
            kb_lock=kb_lock,
            logger=logging.getLogger(),
        )

        # UI 10 -> HW speed = 11 - 10 = 1 (fastest)
        assert captured_kwargs["speed"] == 1
        assert result == "payload"

    def test_slowest_speed_conversion(self):
        """UI speed 0/1 (slowest) should map to HW speed 10 (slowest)."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="rainbow",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness"),
            ui_speed=1,  # slowest in UI
            brightness=50,
            current_color=(0, 255, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        # UI 1 -> HW speed = 11 - 1 = 10 (slowest)
        assert captured_kwargs["speed"] == 10

    def test_passes_brightness_unchanged(self):
        """Brightness should be passed through as-is."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="marquee",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness"),
            ui_speed=5,
            brightness=75,
            current_color=(0, 0, 255),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["brightness"] == 75

    def test_breathing_effect_sets_palette_color(self):
        """Breathing effect should program palette slot and use slot index."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        kb_lock = RLock()

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="breathing",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness", "color"),
            ui_speed=5,
            brightness=50,
            current_color=(255, 128, 64),
            hw_colors={"red": 3},  # Use palette slot 3
            kb=mock_kb,
            kb_lock=kb_lock,
            logger=logging.getLogger(),
        )

        # Should program palette slot 3 with the current color
        mock_kb.set_palette_color.assert_called_once_with(3, (255, 128, 64))
        # Should pass slot index as color parameter
        assert captured_kwargs["color"] == 3

    def test_direct_rgb_backend_passes_effect_color_tuple(self):
        """Backends without palette slots should receive direct RGB tuples."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        result = build_hw_effect_payload(
            effect_name="breathing",
            effect_func=_descriptor(lambda **kwargs: kwargs, "speed", "brightness", "color"),
            ui_speed=5,
            brightness=50,
            current_color=(9, 8, 7),
            hw_colors={},
            kb=mock_kb,
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        mock_kb.set_palette_color.assert_not_called()
        assert result["color"] == (9, 8, 7)

    def test_passes_direction_when_effect_builder_supports_it(self):
        """Directional backends should receive the chosen direction."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        result = build_hw_effect_payload(
            effect_name="wave",
            effect_func=_descriptor(lambda **kwargs: kwargs, "speed", "brightness", "direction"),
            ui_speed=5,
            brightness=40,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
            direction="down_right",
        )

        assert result["direction"] == "down_right"

    def test_accepts_typed_hardware_effect_descriptor(self):
        """Payload builder should work with typed backend effect descriptors."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        descriptor = _descriptor(lambda **kwargs: {"name": "wave", **kwargs}, "speed", "brightness", "color", "direction")

        result = build_hw_effect_payload(
            effect_name="wave",
            effect_func=descriptor,
            ui_speed=5,
            brightness=40,
            current_color=(1, 2, 3),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
            direction="left",
        )

        assert result["name"] == "wave"
        assert result["color"] == (1, 2, 3)
        assert result["direction"] == "left"

    def test_retries_on_unsupported_kwarg_error(self):
        """Should retry with fewer kwargs when 'attr is not needed' error occurs."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        call_count = 0

        def failing_then_succeeding_func(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: reject 'brightness'
                if "brightness" in kwargs:
                    raise ValueError("'brightness' attr is not needed by effect")
            return kwargs

        result = build_hw_effect_payload(
            effect_name="test",
            effect_func=_descriptor(failing_then_succeeding_func, "speed", "brightness"),
            ui_speed=5,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        # Should have retried and succeeded without 'brightness'
        assert call_count == 2
        assert "brightness" not in result
        assert "speed" in result

    def test_filters_kwargs_by_descriptor_supported_keys(self):
        """Should pre-filter kwargs using explicit descriptor metadata."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        result = build_hw_effect_payload(
            effect_name="test",
            effect_func=_descriptor(lambda **kwargs: kwargs, "speed"),
            ui_speed=5,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        # Should have filtered to only 'speed' based on descriptor metadata
        assert "speed" in result
        assert "brightness" not in result

    def test_raises_on_unexpected_error(self):
        """Should raise ValueError immediately for errors that don't match retry pattern."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        def always_failing_func(**kwargs):
            raise ValueError("Unexpected error format")

        with pytest.raises(ValueError, match="Unexpected error format"):
            build_hw_effect_payload(
                effect_name="test",
                effect_func=_descriptor(always_failing_func, "speed", "brightness"),
                ui_speed=5,
                brightness=50,
                current_color=(0, 0, 0),
                hw_colors={},
                kb=MagicMock(),
                kb_lock=RLock(),
                logger=logging.getLogger(),
            )

    def test_clamps_speed_to_valid_range(self):
        """Speed should be clamped to [0, 10]."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        # Test upper bound: UI 15 -> HW speed should clamp to 0 (max(0, 11-15) = 0)
        build_hw_effect_payload(
            effect_name="test",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness"),
            ui_speed=15,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["speed"] == 0

        # Test lower bound: UI -5 -> HW speed should clamp to 10 (min(10, 11-(-5)) = 10)
        build_hw_effect_payload(
            effect_name="test",
            effect_func=_descriptor(capture_effect_func, "speed", "brightness"),
            ui_speed=-5,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["speed"] == 10
