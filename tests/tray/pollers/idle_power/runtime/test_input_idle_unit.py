from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import src.tray.pollers.idle_power._input_idle as input_idle


@dataclass
class _FakeDevice:
    path: str
    events: list[object]
    closed: bool = False

    def close(self) -> None:
        self.closed = True

    def read(self) -> Iterable[object]:
        # Return a copy and clear so repeated reads do not re-report activity.
        out = list(self.events)
        self.events.clear()
        return out


@dataclass
class _FakeEvdevModule:
    device_paths: list[str]
    opened: dict[str, _FakeDevice] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.opened = {}

    def list_devices(self) -> list[str]:
        return list(self.device_paths)

    def InputDevice(self, path: str) -> _FakeDevice:
        dev = _FakeDevice(path=path, events=[])
        self.opened[path] = dev
        return dev


def _make_tracker(
    *,
    device_paths: list[str],
    input_device_paths: set[str] | None = None,
    monotonic_sequence: list[float] | None = None,
) -> tuple[input_idle.InputIdleTracker, _FakeEvdevModule]:
    evdev_mod = _FakeEvdevModule(device_paths=device_paths)

    if input_device_paths is None:
        input_device_paths = set(device_paths)

    def open_device(path: str) -> _FakeDevice:
        return evdev_mod.InputDevice(path)

    def is_input(path: str) -> bool:
        return path in input_device_paths

    monotonic_iter = iter(monotonic_sequence or [0.0])

    def monotonic_fn() -> float:
        try:
            return float(next(monotonic_iter))
        except StopIteration:
            return 999.0

    tracker = input_idle.InputIdleTracker(
        monotonic_fn=monotonic_fn,
        list_devices_fn=evdev_mod.list_devices,
        open_device_fn=open_device,
        is_input_device_fn=is_input,
        select_fn=lambda r, w, x, t: ([d for d in r if getattr(d, "events", [])], [], []),
    )
    return tracker, evdev_mod


def test_seconds_since_activity_returns_none_when_no_devices() -> None:
    tracker, _ = _make_tracker(device_paths=[])

    assert tracker.seconds_since_activity() is None


def test_seconds_since_activity_returns_increasing_idle_when_no_events() -> None:
    # Sequence: init, first now, first refresh, first read, second now, second read.
    tracker, _ = _make_tracker(
        device_paths=["/dev/input/event0"],
        monotonic_sequence=[0.0, 1.0, 2.0, 5.0, 10.0, 10.0],
    )

    assert tracker.seconds_since_activity() == 5.0
    assert tracker.seconds_since_activity() == 10.0


def test_seconds_since_activity_resets_on_input_event() -> None:
    # Sequence: init, first now, first refresh, first read, second now/event,
    # second read, third now, third read.
    tracker, evdev = _make_tracker(
        device_paths=["/dev/input/event0"],
        monotonic_sequence=[0.0, 1.0, 2.0, 5.0, 6.0, 6.0, 12.0, 12.0],
    )

    assert tracker.seconds_since_activity() == 5.0

    evdev.opened["/dev/input/event0"].events.append(object())
    # Event resets idle to the current moment, so idle appears ~0 right away.
    assert tracker.seconds_since_activity() == 0.0

    # After the event is drained, idle grows from the new baseline.
    assert tracker.seconds_since_activity() == 6.0


def test_close_releases_devices() -> None:
    tracker, evdev = _make_tracker(device_paths=["/dev/input/event0"])

    tracker.seconds_since_activity()
    assert "/dev/input/event0" in evdev.opened

    tracker.close()
    assert evdev.opened["/dev/input/event0"].closed is True


def test_only_user_input_devices_are_opened() -> None:
    tracker, evdev = _make_tracker(
        device_paths=["/dev/input/event0", "/dev/input/event1"],
        input_device_paths={"/dev/input/event1"},
    )

    tracker.seconds_since_activity()
    assert "/dev/input/event0" not in evdev.opened
    assert "/dev/input/event1" in evdev.opened


def test_open_failure_is_skipped() -> None:
    def failing_open(path: str) -> _FakeDevice:
        raise OSError("permission denied")

    evdev_mod = _FakeEvdevModule(device_paths=["/dev/input/event0"])
    tracker = input_idle.InputIdleTracker(
        monotonic_fn=lambda: 0.0,
        list_devices_fn=evdev_mod.list_devices,
        open_device_fn=failing_open,
        is_input_device_fn=lambda _path: True,
        select_fn=lambda _r, _w, _x, _t: ([], [], []),
    )

    assert tracker.seconds_since_activity() is None
