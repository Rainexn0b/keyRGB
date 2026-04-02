#!/usr/bin/env python3
"""Unit tests for reactive effect helper math.

These tests avoid running the infinite reactive loops; they validate that the
core computations produce non-trivial overlays.
"""

from __future__ import annotations

import logging


class TestRippleWeight:
    def test_weight_is_zero_far_from_ring(self):
        from src.core.effects.reactive.effects import _ripple_weight

        w = _ripple_weight(d=10, radius=2.0, intensity=1.0, band=1.35)
        assert w == 0.0

    def test_weight_is_positive_on_ring(self):
        from src.core.effects.reactive.effects import _ripple_weight

        w = _ripple_weight(d=3, radius=3.0, intensity=0.8, band=1.35)
        assert w > 0.0


class TestRippleRadius:
    def test_radius_interpolates(self):
        from src.core.effects.reactive.effects import _ripple_radius

        assert _ripple_radius(age_s=0.0, ttl_s=1.0, min_radius=0.0, max_radius=8.0) == 0.0
        assert _ripple_radius(age_s=1.0, ttl_s=1.0, min_radius=0.0, max_radius=8.0) == 8.0
        mid = _ripple_radius(age_s=0.5, ttl_s=1.0, min_radius=0.0, max_radius=8.0)
        assert 3.9 < mid < 4.1

def test_set_reactive_active_pulse_mix_logs_traceback_when_cache_write_fails(caplog) -> None:
    from src.core.effects.reactive import effects

    class _BrokenEngine:
        def __init__(self) -> None:
            object.__setattr__(self, "_reactive_active_pulse_mix", 0.25)

        def __setattr__(self, name: str, value) -> None:
            if name == "_reactive_active_pulse_mix":
                raise RuntimeError("cache write failed")
            object.__setattr__(self, name, value)

    engine = _BrokenEngine()

    with caplog.at_level(logging.ERROR, logger="src.core.effects.reactive.effects"):
        effects._set_reactive_active_pulse_mix(engine, target=1.0)

    assert engine._reactive_active_pulse_mix == 0.25

    records = [
        record
        for record in caplog.records
        if "Failed to cache reactive pulse mix" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None

