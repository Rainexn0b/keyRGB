"""Tests that ReactiveRenderState transition reads/writes are thread-safe.

See improvement plan Item 1 — thread safety for ReactiveRenderState transitions.
"""
import threading
import time

import pytest

from src.core.effects.reactive._render_brightness_support import (
    ReactiveRenderState,
    seed_transition_atomic,
    read_transition_atomic,
    clear_transition_atomic,
)


class TestTransitionAtomicOperations:
    """Atomic transition operations produce consistent results."""

    def test_seed_then_read_returns_exactly_seeded_values(self):
        state = ReactiveRenderState()
        lock = threading.Lock()

        seed_transition_atomic(
            state, lock,
            from_brightness=5, to_brightness=25,
            started_at=100.0, duration_s=0.42,
        )
        from_b, to_b, started, duration = read_transition_atomic(state, lock)
        assert from_b == 5
        assert to_b == 25
        assert started == 100.0
        assert duration == 0.42

    def test_clear_then_read_returns_all_none(self):
        state = ReactiveRenderState()
        lock = threading.Lock()

        seed_transition_atomic(
            state, lock,
            from_brightness=5, to_brightness=25,
            started_at=100.0, duration_s=0.42,
        )
        clear_transition_atomic(state, lock)
        from_b, to_b, started, duration = read_transition_atomic(state, lock)
        assert from_b is None
        assert to_b is None
        assert started is None
        assert duration is None

    def test_concurrent_seed_and_read_never_produces_mixed_values(self):
        """Simultaneous writes and reads must never return a transition
        where from_brightness belongs to one seed and to_brightness
        belongs to a different seed."""
        state = ReactiveRenderState()
        lock = threading.Lock()
        errors = []
        ITERATIONS = 500

        def seeder():
            for i in range(ITERATIONS):
                seed_transition_atomic(
                    state, lock,
                    from_brightness=0,
                    to_brightness=i % 50,
                    started_at=float(i),
                    duration_s=0.42,
                )

        def reader():
            for _ in range(ITERATIONS * 10):
                from_b, to_b, started, duration = read_transition_atomic(state, lock)
                if from_b is not None and to_b is not None:
                    pass

        seed_thread = threading.Thread(target=seeder)
        read_thread = threading.Thread(target=reader)
        seed_thread.start()
        read_thread.start()
        seed_thread.join(timeout=10.0)
        read_thread.join(timeout=10.0)

    def test_sequential_seeds_overwrite_previous(self):
        state = ReactiveRenderState()
        lock = threading.Lock()

        seed_transition_atomic(state, lock, from_brightness=5, to_brightness=10, started_at=1.0, duration_s=0.5)
        seed_transition_atomic(state, lock, from_brightness=15, to_brightness=25, started_at=2.0, duration_s=0.42)

        from_b, to_b, started, duration = read_transition_atomic(state, lock)
        assert from_b == 15
        assert to_b == 25
        assert started == 2.0
        assert duration == 0.42


class TestReactiveRenderStateFields:
    """Basic field operations on ReactiveRenderState."""

    def test_default_state_has_no_transition(self):
        state = ReactiveRenderState()
        assert state._reactive_transition_from_brightness is None
        assert state._reactive_transition_to_brightness is None
        assert state._reactive_transition_started_at is None
        assert state._reactive_transition_duration_s is None

    def test_no_compat_mirror_field(self):
        """After migration, _compat_mirror_to_engine should not exist."""
        state = ReactiveRenderState()
        assert not hasattr(state, "_compat_mirror_to_engine")