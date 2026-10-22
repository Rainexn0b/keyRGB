"""Any-input wake accepts event evidence, never fd readiness or startup time."""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from keyrgb.tray.pollers.idle_power import _input_idle as inputs


@dataclass
class Event:
    type: int
    code: int
    value: int
    at: float = 105.0

    def timestamp(self):
        return self.at


@pytest.mark.parametrize(
    "kind,code,value,accepted",
    [
        (1, 29, 1, True),  # Ctrl
        (1, 42, 1, True),  # Shift
        (1, 56, 1, True),  # Alt
        (1, 125, 1, True),  # Meta (including a gesture-generated Meta)
        (1, 272, 1, True),  # Mouse click
        (1, 330, 1, True),  # Touchpad contact
        (2, 0, 4, True),  # Relative movement
        (2, 8, -1, True),  # Scroll
        (3, 0x35, 200, True),  # Multitouch position
        (3, 0x39, 7, True),  # New contact
        (0, 0, 0, False),  # Synchronization
        (4, 4, 125, False),  # Scan-code metadata
        (17, 0, 1, False),  # LED state
        (1, 42, 0, False),  # Release
        (1, 42, 2, False),  # Held-key repeat
        (2, 0, 0, False),  # No movement
        (3, 0x39, -1, False),  # Contact removed
        (3, 0x3A, 10, False),  # Pressure-only noise
    ],
)
def test_only_meaningful_input_events_qualify(kind, code, value, accepted):
    assert bool(inputs._wake_activity_time(Event(kind, code, value), now=110)) is accepted


def test_input_tracker_retains_kernel_time_and_ignores_empty_ready_fd():
    events = []
    device = SimpleNamespace(path="touchpad", read=lambda: list(events), close=lambda: None)
    tracker = inputs.InputIdleTracker(
        monotonic_fn=lambda: 110.0,
        list_devices_fn=lambda: ["touchpad"],
        open_device_fn=lambda _: device,
        is_input_device_fn=lambda _: True,
        is_keyboard_device_fn=lambda _: False,
        set_event_clock_fn=lambda _: True,
        select_fn=lambda *_: ([device], [], []),
    )
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 0.0
    # An event queued before sleep at 100 must not become new input at poll 110.
    events.append(Event(2, 0, 4, at=95.0))
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 95.0
    events[:] = [Event(1, 125, 1)]
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 105.0
    assert tracker.last_keyboard_activity_at == 0.0
    events[:] = [Event(0, 3, 0), Event(3, 0x35, 200, at=108)]  # SYN_DROPPED + stale state
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 105.0
    events[:] = [Event(3, 0x35, 205, at=109), Event(0, 0, 0)]
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 105.0
    events[:] = [Event(2, 0, 3, at=110)]
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 110.0
    tracker.close()


def test_untrusted_clock_cannot_produce_any_input_wake():
    device = SimpleNamespace(path="keyboard", read=lambda: [Event(1, 42, 1)], close=lambda: None)
    tracker = inputs.InputIdleTracker(
        monotonic_fn=lambda: 110.0,
        list_devices_fn=lambda: ["keyboard"],
        open_device_fn=lambda _: device,
        is_input_device_fn=lambda _: True,
        is_keyboard_device_fn=lambda _: True,
        set_event_clock_fn=lambda _: False,
        select_fn=lambda *_: ([device], [], []),
    )
    tracker.seconds_since_activity()
    assert tracker.last_wake_activity_at == 0.0
    tracker.close()


def test_event_clock_is_fd_local_and_failure_is_nonfatal(monkeypatch):
    ioctl = Mock()
    monkeypatch.setattr(inputs.fcntl, "ioctl", ioctl)
    assert inputs._set_monotonic_event_clock(SimpleNamespace(fd=8))
    ioctl.assert_called_once_with(8, 0x400445A0, struct.pack("i", time.CLOCK_MONOTONIC))
    ioctl.side_effect = OSError("unsupported")
    assert not inputs._set_monotonic_event_clock(SimpleNamespace(fd=8))


@pytest.mark.parametrize("at", [0.0, float("nan"), float("inf"), 2_000_000_000.0])
def test_invalid_or_wrong_clock_timestamps_do_not_wake(at):
    assert inputs._wake_activity_time(Event(1, 42, 1, at=at), now=110) == 0.0
