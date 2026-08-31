from __future__ import annotations

import threading
from threading import Event, Lock, Thread

import pytest

from keyrgb.core.effects.device import NullKeyboard
from keyrgb.core.effects.engine import EffectsEngine


class _ObservableStartLock:
    """Lifecycle lock that parks the first acquire so a second start is observed.

    Reproduces the exact concurrency KSW-5 targets without any sleep-based
    scheduling: the first ``start_effect`` holds the lifecycle lock across its
    whole stop/configure/publish region while the second ``start_effect`` is
    left parked at the lock. Releasing the gate lets the first publish its
    worker; the second must then stop that worker before publishing its own.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self.first_acquired = Event()
        self.release_first = Event()
        self._armed = True

    def __enter__(self) -> None:
        self._lock.acquire()
        if self._armed:
            self._armed = False
            self.first_acquired.set()
            assert self.release_first.wait(timeout=5.0), "first start_effect never released the lifecycle lock"

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._lock.release()
        return False


def test_concurrent_starts_publish_exactly_one_live_worker() -> None:
    """Two racing direct starts must end with one live worker and no orphan.

    Without the KSW-5 lifecycle lock, both starts could clear the previous
    worker and publish their own software worker, orphaning the first as a
    second live deck writer that keeps repainting forever. With the lock the
    region is atomic: the second start stops the first's worker before it
    publishes.
    """

    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    obs = _ObservableStartLock()
    engine._start_lock = obs  # type: ignore[assignment]

    published: list[Thread] = []
    orig_start_sw = engine._start_sw_effect

    def _spy_start_sw(*, target, prev_color, fade_to_color, from_sw_effect=False) -> None:
        orig_start_sw(
            target=target,
            prev_color=prev_color,
            fade_to_color=fade_to_color,
            from_sw_effect=from_sw_effect,
        )
        published.append(engine.thread)

    engine._start_sw_effect = _spy_start_sw  # type: ignore[assignment]

    first = threading.Thread(
        target=lambda: engine.start_effect("rainbow_wave", speed=0, brightness=25, color=(255, 0, 0)),
        daemon=True,
    )
    second = threading.Thread(
        target=lambda: engine.start_effect("spectrum_cycle", speed=0, brightness=25, color=(0, 255, 0)),
        daemon=True,
    )

    first.start()
    assert obs.first_acquired.wait(timeout=5.0), "first start_effect never acquired the lifecycle lock"

    # First start holds the lock; second start is now parked at the lock.
    second.start()

    # Let the first complete its full region and publish its worker.
    obs.release_first.set()
    first.join(timeout=5.0)
    assert not first.is_alive(), "first start_effect did not finish"
    second.join(timeout=5.0)
    assert not second.is_alive(), "second start_effect did not finish"

    # Both starts published a worker, in order.
    assert len(published) == 2, published
    first_worker, second_worker = published

    # The first worker was stopped by the second start's serialized stop().
    assert not first_worker.is_alive(), "stale worker was not stopped"
    # Exactly one live worker exists, and it is the current engine worker.
    live = [t for t in published if t.is_alive()]
    assert live == [second_worker], live
    assert engine.thread is second_worker

    # Stop cleanup: stopping the engine clears the current worker reference and
    # leaves no live workers behind.
    engine.stop()
    assert engine.thread is None
    assert engine.stop_event.is_set() is False
    assert all(not t.is_alive() for t in published)


def test_start_effect_refuses_replacement_under_lifecycle_lock() -> None:
    """Previous-worker timeout refusal (existing behavior) must survive KSW-5.

    A start that published a worker which ignores stop_event must still be
    refused by the next start, even though both now run under the lifecycle
    lock. This pins the refusal path so the lock wrapper cannot accidentally
    swallow it.
    """

    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    stubborn: list[Thread] = []
    stubborn_blocks: list[Event] = []

    def _publish_stubborn(*, target, prev_color, fade_to_color, from_sw_effect=False) -> None:
        del target, prev_color, fade_to_color, from_sw_effect
        block = Event()
        stubborn_blocks.append(block)

        def _run() -> None:
            block.wait(timeout=10.0)

        t = Thread(target=_run, daemon=True)
        t.start()
        engine.thread = t
        engine.running = True
        stubborn.append(t)

    engine._start_sw_effect = _publish_stubborn  # type: ignore[assignment]

    engine.start_effect("rainbow_wave", speed=0, brightness=25, color=(255, 0, 0))
    assert len(stubborn) == 1
    assert engine.thread is stubborn[0]

    with pytest.raises(RuntimeError, match="Previous effect thread is still stopping"):
        engine.start_effect("spectrum_cycle", speed=0, brightness=25, color=(0, 255, 0))

    # Refusal left the previous (still-stuck) worker as the sole published one.
    assert engine.thread is stubborn[0]
    assert engine.stop_event.is_set() is True

    # Release the stubborn worker so it cannot leak into other tests.
    for block in stubborn_blocks:
        block.set()
    for t in stubborn:
        t.join(timeout=2.0)


def test_start_lock_is_distinct_from_keyboard_lock() -> None:
    """The engine owns a real lifecycle lock separate from hardware I/O.

    The lock must exist on a constructed engine and must not be the same object
    as kb_lock, so start_effect can retain lifecycle ownership while stop() joins
    a worker without preventing that worker from completing final hardware I/O.
    """

    engine = EffectsEngine()
    # threading.Lock is a factory on 3.10–3.12 and a type on 3.13+.
    assert isinstance(engine._start_lock, type(Lock()))
    assert engine._start_lock is not engine.kb_lock

    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.start_effect("rainbow_wave", speed=0, brightness=25, color=(255, 0, 0))
    engine.stop()
    assert engine.thread is None
