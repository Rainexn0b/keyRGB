"""Controller wake-settle hardware-poller integration (tray stage 1).

Split from ``test_controller_wake_settle_unit.py`` for the release LOC gate;
covers the poller loop while a settle deadline is armed: USB reads are
skipped during settle, the loop waits for the exact remaining deadline
shutdown-interruptibly, a due settle bypasses reactive deferral, and the
ordinary wait is chunked so a cross-thread evdev arm is noticed without
fast-cadence USB reads (including the frozen-clock chunk-budget bound).
"""

from __future__ import annotations

import threading

import pytest

from tests.tray.pollers.hardware.lifecycle.wake_settle._support import (
    _capture_poll_target,
    _SettleTray,
    install_monotonic_clock,
)


@pytest.fixture
def clock(monkeypatch):
    return install_monotonic_clock(monkeypatch)


def test_poller_skips_usb_reads_and_waits_exact_remaining(monkeypatch, clock) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

    tray = _SettleTray()
    assert arm_controller_wake_settle(tray, now=100.0) is True

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        if len(sleep_calls) >= 8:
            raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    target = _capture_poll_target(monkeypatch, tray)

    with pytest.raises(KeyboardInterrupt):
        target()

    # The exact 2s deadline is chunked at the 0.25s state-check cadence with
    # no USB reads in between.
    assert sleep_calls == [pytest.approx(0.25)] * 8
    assert tray.kb.reads == 0


def test_poller_settle_wait_notices_cancellation_without_usb_reads(monkeypatch, clock) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.pollers.hardware._controller_sleep import (
        arm_controller_wake_settle,
        clear_controller_wake_settle,
        controller_wake_settle_pending,
    )

    tray = _SettleTray()
    assert arm_controller_wake_settle(tray, now=100.0) is True
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", lambda *_a, **_kw: (0, True))

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        if len(sleep_calls) == 2:
            # Simulate a manual/power intent cancelling the deadline from
            # another thread.
            clear_controller_wake_settle(tray)
        if len(sleep_calls) >= 3:
            raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    target = _capture_poll_target(monkeypatch, tray)

    with pytest.raises(KeyboardInterrupt):
        target()

    assert controller_wake_settle_pending(tray) is False
    # Two settle chunks, then the ordinary wait (also 0.25-chunked while
    # controller-sleep-active) ends the drive.
    assert sleep_calls == [pytest.approx(0.25)] * 3
    # Exactly one post-cancellation verification poll (get + is_off).
    assert tray.kb.reads == 2


def test_poller_settle_wait_is_shutdown_interruptible(monkeypatch, clock) -> None:
    import time as stdlib_time

    from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

    tray = _SettleTray()
    tray._polling_shutdown_event = threading.Event()
    assert arm_controller_wake_settle(tray, now=100.0) is True

    # Shutdown arrives mid-settle from another thread; the exact-deadline
    # wait must abort instead of sleeping through the full 2s.
    timer = threading.Timer(0.05, tray._polling_shutdown_event.set)
    timer.start()
    try:
        target = _capture_poll_target(monkeypatch, tray)
        started = stdlib_time.perf_counter()
        assert target() is None
        elapsed = stdlib_time.perf_counter() - started
    finally:
        timer.join()

    assert elapsed < 1.5
    assert tray.kb.reads == 0


def test_poller_due_settle_bypasses_reactive_deferral(monkeypatch, clock) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

    tray = _SettleTray()
    assert arm_controller_wake_settle(tray, now=98.0) is True

    defer_calls: list[bool] = []
    apply_calls: list[tuple] = []

    def fake_should_defer(**kwargs) -> bool:
        defer_calls.append(True)
        return True

    def fake_apply(*args, **kwargs):
        apply_calls.append((args, kwargs))
        return (1, False)

    monkeypatch.setattr(hp, "_should_defer_poll_for_reactive_pulses", fake_should_defer)
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", fake_apply)

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        if len(sleep_calls) >= 8:
            raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    target = _capture_poll_target(monkeypatch, tray)

    with pytest.raises(KeyboardInterrupt):
        target()

    assert len(apply_calls) == 1
    assert defer_calls == []
    # A due restart failure/pending retry keeps the ordinary 2s cadence;
    # state checks are chunked, but hardware is not restart-spammed at 4Hz.
    assert sleep_calls == [pytest.approx(0.25)] * 8


def test_poller_chunked_wait_detects_evdev_arm_without_fast_reads(monkeypatch, clock) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

    tray = _SettleTray()
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", lambda *_a, **_kw: (0, True))

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        if len(sleep_calls) == 1:
            # Simulate an evdev wake from another thread arming the settle.
            assert arm_controller_wake_settle(tray, now=100.0) is True
        else:
            raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    target = _capture_poll_target(monkeypatch, tray)

    with pytest.raises(KeyboardInterrupt):
        target()

    assert sleep_calls == [pytest.approx(0.25), pytest.approx(0.25)]
    # Exactly one coherent snapshot (get_brightness + is_off): the ordinary
    # chunked wait and the chunked settle wait performed no fast-cadence
    # USB reads.
    assert tray.kb.reads == 2


def test_poller_chunk_budget_bounds_frozen_clock_iterations(monkeypatch, clock) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    tray = _SettleTray()
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", lambda *_a, **_kw: (0, True))

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        if len(sleep_calls) >= 9:
            raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    target = _capture_poll_target(monkeypatch, tray)

    with pytest.raises(KeyboardInterrupt):
        target()

    # One ordinary 2s interval is exactly eight 0.25s chunks even though the
    # frozen test clock never advances; the 9th chunk starts the next cycle.
    assert sleep_calls == [pytest.approx(0.25)] * 9
    # Two coherent snapshots total (get_brightness + is_off each).
    assert tray.kb.reads == 4
