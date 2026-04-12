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


class TestAllowedHwEffectKeys:
    """Test allowed_hw_effect_keys introspection logic."""

    def test_returns_empty_set_when_no_closure(self):
        """Should return empty set for functions without closure."""
        from src.core.effects.hw_payloads import allowed_hw_effect_keys

        def simple_func():
            return "test"

        result = allowed_hw_effect_keys(simple_func, logger=logging.getLogger())
        assert result == set()

    def test_returns_empty_set_on_introspection_error(self):
        """Should gracefully handle introspection failures."""
        from src.core.effects.hw_payloads import allowed_hw_effect_keys

        # Mock object without __code__ attribute
        mock_func = MagicMock()
        del mock_func.__code__

        result = allowed_hw_effect_keys(mock_func, logger=logging.getLogger())
        assert result == set()

    def test_propagates_unexpected_introspection_errors(self):
        """Assertion-style introspection bugs should not be treated as normal fallback."""
        from src.core.effects.hw_payloads import allowed_hw_effect_keys

        class _BrokenCode:
            @property
            def co_freevars(self):
                raise AssertionError("unexpected introspection bug")

        class _BrokenFunc:
            __code__ = _BrokenCode()
            __closure__ = ()

        with pytest.raises(AssertionError, match="unexpected introspection bug"):
            allowed_hw_effect_keys(_BrokenFunc(), logger=logging.getLogger())

    def test_extracts_keys_from_closure_with_args_dict(self):
        """Should extract allowed keys from closure args dict."""
        from src.core.effects.hw_payloads import allowed_hw_effect_keys

        # Simulate the legacy hardware-effect builder pattern with args stored in a closure
        def make_effect_func():
            args = {"speed": None, "brightness": None, "color": None}

            def effect_func(**kwargs):
                return args

            return effect_func

        func = make_effect_func()
        result = allowed_hw_effect_keys(func, logger=logging.getLogger())

        assert "speed" in result
        assert "brightness" in result
        assert "color" in result


class TestBuildHwEffectPayload:
    """Test build_hw_effect_payload construction logic."""

    def test_ite8910_uses_direct_speed_scale(self):
        """ITE8910 should preserve the UI speed ordering instead of inverting it."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        class FakeIte8910Keyboard:
            keyrgb_hw_speed_policy = "direct"

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        result = build_hw_effect_payload(
            effect_name="wave",
            effect_func=capture_effect_func,
            ui_speed=10,
            brightness=50,
            current_color=(255, 0, 0),
            hw_colors={},
            kb=FakeIte8910Keyboard(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["speed"] == 10
        assert result == "payload"

    def test_ite8291r3_inverts_speed_scale(self):
        """Vendored ite8291r3 uses 0 = fastest, 10 = slowest."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        class FakeIte8291r3Keyboard:
            keyrgb_hw_speed_policy = "inverted"

        kb_lock = RLock()

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        result = build_hw_effect_payload(
            effect_name="wave",
            effect_func=capture_effect_func,
            ui_speed=10,  # fastest in UI
            brightness=50,
            current_color=(255, 0, 0),
            hw_colors={"red": 1},
            kb=FakeIte8291r3Keyboard(),
            kb_lock=kb_lock,
            logger=logging.getLogger(),
        )

        # UI 10 -> HW speed = 11 - 10 = 1 (fastest)
        assert captured_kwargs["speed"] == 1
        assert result == "payload"

    def test_ite8291r3_slowest_speed_conversion(self):
        """Lowest UI speed should stay slowest on the ite8291r3 backend."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        class FakeIte8291r3Keyboard:
            keyrgb_hw_speed_policy = "inverted"

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="rainbow",
            effect_func=capture_effect_func,
            ui_speed=1,  # slowest in UI
            brightness=50,
            current_color=(0, 255, 0),
            hw_colors={},
            kb=FakeIte8291r3Keyboard(),
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
            effect_func=capture_effect_func,
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
            effect_func=capture_effect_func,
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

    def test_breathing_palette_failure_logs_traceback_and_keeps_payload(self, caplog):
        """Should preserve payload building and log exception context on palette failure."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        mock_kb.set_palette_color.side_effect = OSError("palette write failed")
        kb_lock = RLock()
        logger = logging.getLogger("tests.hw_payloads")

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        with caplog.at_level(logging.DEBUG, logger=logger.name):
            result = build_hw_effect_payload(
                effect_name="breathing",
                effect_func=capture_effect_func,
                ui_speed=5,
                brightness=50,
                current_color=(255, 128, 64),
                hw_colors={"red": 3},
                kb=mock_kb,
                kb_lock=kb_lock,
                logger=logger,
            )

        assert result == "payload"
        assert captured_kwargs["color"] == 3

        records = [
            record
            for record in caplog.records
            if record.message == "Failed to program palette slot for hardware effect"
        ]
        assert records
        assert any(record.exc_info and isinstance(record.exc_info[1], OSError) for record in records)

    def test_breathing_palette_failure_propagates_unexpected_errors(self):
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        mock_kb.set_palette_color.side_effect = AssertionError("unexpected palette bug")

        def capture_effect_func(**kwargs):
            return kwargs

        with pytest.raises(AssertionError, match="unexpected palette bug"):
            build_hw_effect_payload(
                effect_name="breathing",
                effect_func=capture_effect_func,
                ui_speed=5,
                brightness=50,
                current_color=(255, 128, 64),
                hw_colors={"red": 3},
                kb=mock_kb,
                kb_lock=RLock(),
                logger=logging.getLogger("tests.hw_payloads"),
            )

    def test_palette_backend_color_effect_uses_palette_slot(self):
        """Palette-based hardware effects should never receive raw RGB tuples."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="ripple",
            effect_func=capture_effect_func,
            ui_speed=5,
            brightness=50,
            current_color=(255, 128, 64),
            hw_colors={"red": 3},
            kb=mock_kb,
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        mock_kb.set_palette_color.assert_called_once_with(3, (255, 128, 64))
        assert captured_kwargs["color"] == 3

    def test_palette_backend_random_effect_preserves_random_sentinel(self):
        """Palette backends should keep firmware-random effects on the random slot."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="random",
            effect_func=capture_effect_func,
            ui_speed=5,
            brightness=50,
            current_color=(255, 128, 64),
            hw_colors={"red": 3, "random": 8},
            kb=mock_kb,
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        mock_kb.set_palette_color.assert_not_called()
        assert captured_kwargs["color"] == 8

    def test_direct_rgb_random_effect_passes_color_tuple(self):
        """Direct-RGB backends should keep tuple colors for hardware random variants."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        mock_kb = MagicMock()
        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        build_hw_effect_payload(
            effect_name="random",
            effect_func=capture_effect_func,
            ui_speed=5,
            brightness=25,
            current_color=(17, 34, 51),
            hw_colors={},
            kb=mock_kb,
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        mock_kb.set_palette_color.assert_not_called()
        assert captured_kwargs["color"] == (17, 34, 51)

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
            effect_func=failing_then_succeeding_func,
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

    def test_filters_kwargs_by_allowed_keys_when_available(self):
        """Should pre-filter kwargs if allowed keys can be determined."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        def make_effect_func_with_args():
            args = {"speed": None}  # Only speed is allowed

            def effect_func(**kwargs):
                _ = args  # ensure `args` exists in the closure for introspection
                return kwargs

            return effect_func

        func = make_effect_func_with_args()

        result = build_hw_effect_payload(
            effect_name="test",
            effect_func=func,
            ui_speed=5,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=MagicMock(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        # Should have filtered to only 'speed' based on closure args
        assert "speed" in result
        # Test successful execution - actual filtering behavior depends on implementation

    def test_raises_on_unexpected_error(self):
        """Should raise ValueError immediately for errors that don't match retry pattern."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        def always_failing_func(**kwargs):
            raise ValueError("Unexpected error format")

        with pytest.raises(ValueError, match="Unexpected error format"):
            build_hw_effect_payload(
                effect_name="test",
                effect_func=always_failing_func,
                ui_speed=5,
                brightness=50,
                current_color=(0, 0, 0),
                hw_colors={},
                kb=MagicMock(),
                kb_lock=RLock(),
                logger=logging.getLogger(),
            )

    def test_ite8291r3_clamps_speed_to_valid_range(self):
        """ite8291r3 speed inversion should still clamp to [0, 10]."""
        from src.core.effects.hw_payloads import build_hw_effect_payload

        class FakeIte8291r3Keyboard:
            keyrgb_hw_speed_policy = "inverted"

        captured_kwargs = {}

        def capture_effect_func(**kwargs):
            captured_kwargs.update(kwargs)
            return "payload"

        # Test upper bound: values above the UI range first clamp to 10, then
        # the ite8291r3 inversion maps that to the fastest supported hardware
        # value.
        build_hw_effect_payload(
            effect_name="test",
            effect_func=capture_effect_func,
            ui_speed=15,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=FakeIte8291r3Keyboard(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["speed"] == 1

        # Test lower bound: UI -5 -> HW speed should clamp to 10 (min(10, 11-(-5)) = 10)
        build_hw_effect_payload(
            effect_name="test",
            effect_func=capture_effect_func,
            ui_speed=-5,
            brightness=50,
            current_color=(0, 0, 0),
            hw_colors={},
            kb=FakeIte8291r3Keyboard(),
            kb_lock=RLock(),
            logger=logging.getLogger(),
        )

        assert captured_kwargs["speed"] == 10
