#!/usr/bin/env python3
"""Unit tests for effects/hw_payloads.py - protocol packet construction logic.

Tests focus on the pure data transformation logic for building hardware effect payloads,
avoiding brittle dependencies on specific hardware or UI elements.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock


class TestAllowedHwEffectKeys:
    """Test the explicit accepted-payload metadata contract."""

    def test_returns_empty_set_when_no_closure(self):
        """Should return empty set for functions without closure."""
        from keyrgb.core.effects.hw_payloads import allowed_hw_effect_keys

        def simple_func():
            return "test"

        result = allowed_hw_effect_keys(simple_func, logger=logging.getLogger())
        assert result == set()

    def test_returns_empty_set_without_explicit_contract(self):
        from keyrgb.core.effects.hw_payloads import allowed_hw_effect_keys

        mock_func = MagicMock()

        result = allowed_hw_effect_keys(mock_func, logger=logging.getLogger())
        assert result == set()

    def test_does_not_touch_callable_closure_internals(self):
        from keyrgb.core.effects.hw_payloads import allowed_hw_effect_keys

        class _CallableWithBrokenCode:
            @property
            def __code__(self):
                raise AssertionError("closure internals must not be inspected")

            def __call__(self, **kwargs):
                return kwargs

        assert allowed_hw_effect_keys(_CallableWithBrokenCode(), logger=logging.getLogger()) == set()

    def test_extracts_keys_from_declared_builder_contract(self):
        from keyrgb.core.backends.effect_contract import hardware_effect_builder
        from keyrgb.core.effects.hw_payloads import allowed_hw_effect_keys

        func = hardware_effect_builder(
            lambda **kwargs: kwargs,
            accepted_kwargs=("speed", "brightness", "color"),
        )
        result = allowed_hw_effect_keys(func, logger=logging.getLogger())

        assert "speed" in result
        assert "brightness" in result
        assert "color" in result
