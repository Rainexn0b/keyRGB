#!/usr/bin/env python3
"""Unit tests for _ripple_loop.py engine-attr/writer helpers."""

from __future__ import annotations

from types import SimpleNamespace

# ── Utility: _engine_int_attr_or_default ──────────────────────────────────────


class TestEngineIntAttrOrDefault:
    def test_missing_attribute_returns_missing_default(self):
        from keyrgb.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace()
        assert _engine_int_attr_or_default(engine, "nonexistent", missing_default=42) == 42

    def test_valid_string_attr_returns_int(self):
        from keyrgb.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace(some_attr="5")
        assert _engine_int_attr_or_default(engine, "some_attr", missing_default=0) == 5

    def test_none_attr_returns_zero(self):
        from keyrgb.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace(some_attr=None)
        # int(None or 0) == int(0) == 0, not missing_default
        assert _engine_int_attr_or_default(engine, "some_attr", missing_default=99) == 0


# ── Utility: _engine_int_attr_or_fallback ─────────────────────────────────────


class TestEngineIntAttrOrFallback:
    def test_valid_attr_delegates_to_default(self):
        from keyrgb.core.effects.reactive._ripple_loop import _engine_int_attr_or_fallback

        engine = SimpleNamespace(brightness=25)
        result = _engine_int_attr_or_fallback(engine, "brightness", missing_default=0, error_default=-1)
        assert result == 25

    def test_coercion_error_returns_error_default(self):
        from keyrgb.core.effects.reactive._ripple_loop import _engine_int_attr_or_fallback

        # "not_a_number" is truthy so `int("not_a_number" or 0)` raises ValueError
        engine = SimpleNamespace(bad_attr="not_a_number")
        result = _engine_int_attr_or_fallback(engine, "bad_attr", missing_default=0, error_default=7)
        assert result == 7


# ── Utility: _has_per_key_writer ──────────────────────────────────────────────


class TestHasPerKeyWriter:
    def test_no_set_key_colors_attr_returns_false(self):
        from keyrgb.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(kb=SimpleNamespace())  # no set_key_colors
        assert _has_per_key_writer(engine) is False

    def test_set_key_colors_none_returns_false(self):
        from keyrgb.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(kb=SimpleNamespace(set_key_colors=None))
        assert _has_per_key_writer(engine) is False

    def test_set_key_colors_callable_returns_true(self):
        from keyrgb.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(
            backend_caps=SimpleNamespace(per_key=True),
            kb=SimpleNamespace(set_key_colors=lambda keys: None),
        )
        assert _has_per_key_writer(engine) is True
