"""Unit coverage for WaylandIdleTracker with injected protocol fakes."""

from __future__ import annotations

import sys
import types
from typing import Any, ClassVar

import pytest

from src.tray.pollers.idle_power import _wayland_idle as wayland_idle


class _FakeProxy:
    def __init__(self) -> None:
        self.dispatcher: dict[str, Any] = {}
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class _FakeNotifier(_FakeProxy):
    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[_FakeProxy] = []
        self.last_timeout: int | None = None
        self.last_seat: object | None = None

    def get_idle_notification(self, timeout_ms: int, seat: object) -> _FakeProxy:
        self.last_timeout = timeout_ms
        self.last_seat = seat
        note = _FakeProxy()
        self.notifications.append(note)
        return note


class _FakeRegistry:
    def __init__(self, *, seat_name: int | None = 1, notifier_name: int | None = 2) -> None:
        self.dispatcher: dict[str, Any] = {}
        self.seat_name = seat_name
        self.notifier_name = notifier_name
        self.bound: list[tuple[int, object, object]] = []

    def bind(self, name: int, iface: object, version: object) -> object:
        self.bound.append((name, iface, version))
        if iface is _WlSeat:
            return _FakeProxy()
        if iface is _ExtIdleNotifierV1:
            return _FakeNotifier()
        raise AssertionError(f"unexpected bind {iface}")


class _FakeDisplay:
    instances: ClassVar[list[_FakeDisplay]] = []

    def __init__(self, display_name_or_fd: object = None) -> None:
        self.display_name_or_fd = display_name_or_fd
        self.connected = False
        self.disconnected = False
        self.flushed = 0
        self.read_calls = 0
        self.dispatch_calls = 0
        self._fd = 7
        self.registry = _FakeRegistry()
        self.dispatch_error: Exception | None = None
        self.read_error: Exception | None = None
        self.flush_error: Exception | None = None
        _FakeDisplay.instances.append(self)

    def connect(self) -> None:
        self.connected = True

    def get_registry(self) -> _FakeRegistry:
        return self.registry

    def roundtrip(self) -> None:
        handler = self.registry.dispatcher.get("global")
        if handler is None:
            return
        if self.registry.seat_name is not None:
            handler(self.registry, self.registry.seat_name, _WlSeat.name, 1)
        if self.registry.notifier_name is not None:
            handler(self.registry, self.registry.notifier_name, _ExtIdleNotifierV1.name, 1)

    def flush(self) -> None:
        if self.flush_error is not None:
            raise self.flush_error
        self.flushed += 1

    def get_fd(self) -> int:
        return self._fd

    def read(self) -> None:
        if self.read_error is not None:
            raise self.read_error
        self.read_calls += 1

    def dispatch(self, block: bool = False) -> None:
        if self.dispatch_error is not None:
            raise self.dispatch_error
        self.dispatch_calls += 1

    def disconnect(self) -> None:
        self.disconnected = True


class _WlSeat:
    name = "wl_seat"
    version = 1


class _ExtIdleNotifierV1:
    name = "ext_idle_notifier_v1"
    version = 1


def _install_fake_pywayland(monkeypatch: pytest.MonkeyPatch) -> None:
    client_mod = types.ModuleType("pywayland.client")
    client_mod.Display = _FakeDisplay  # type: ignore[attr-defined]

    ext_mod = types.ModuleType("pywayland.protocol.ext_idle_notify_v1")
    ext_mod.ExtIdleNotifierV1 = _ExtIdleNotifierV1  # type: ignore[attr-defined]

    wayland_mod = types.ModuleType("pywayland.protocol.wayland")
    wayland_mod.WlSeat = _WlSeat  # type: ignore[attr-defined]

    protocol_pkg = types.ModuleType("pywayland.protocol")
    pywayland_pkg = types.ModuleType("pywayland")

    monkeypatch.setitem(sys.modules, "pywayland", pywayland_pkg)
    monkeypatch.setitem(sys.modules, "pywayland.client", client_mod)
    monkeypatch.setitem(sys.modules, "pywayland.protocol", protocol_pkg)
    monkeypatch.setitem(sys.modules, "pywayland.protocol.ext_idle_notify_v1", ext_mod)
    monkeypatch.setitem(sys.modules, "pywayland.protocol.wayland", wayland_mod)


@pytest.fixture(autouse=True)
def _reset_fake_display() -> None:
    _FakeDisplay.instances.clear()


def test_wayland_idle_tracker_connects_and_tracks_idle_events(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pywayland(monkeypatch)
    select_calls: list[object] = []

    def select_fn(rlist: list[object], _w: list[object], _x: list[object], _timeout: float):
        select_calls.append(rlist)
        return rlist, [], []

    tracker = wayland_idle.WaylandIdleTracker(timeout_ms=1500, select_fn=select_fn)
    display = _FakeDisplay.instances[-1]
    assert display.connected is True
    assert tracker.is_idle() is False

    note = tracker._notification
    assert note is not None
    note.dispatcher["idled"](note)
    assert tracker.is_idle() is True

    note.dispatcher["resumed"](note)
    assert tracker.is_idle() is False
    assert select_calls  # select used during read path

    tracker.set_timeout_ms(1500)  # no-op same value
    tracker.set_timeout_ms(2500)
    assert tracker._timeout_ms == 2500
    assert tracker._notification is not None
    assert tracker._notification is not note

    tracker.close()
    assert display.disconnected is True
    assert tracker.is_idle() is None


def test_wayland_idle_tracker_requires_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pywayland(monkeypatch)

    original_init = _FakeDisplay.__init__

    def init_missing(self: _FakeDisplay, display_name_or_fd: object = None) -> None:
        original_init(self, display_name_or_fd)
        self.registry = _FakeRegistry(seat_name=None, notifier_name=None)

    monkeypatch.setattr(_FakeDisplay, "__init__", init_missing)

    with pytest.raises(RuntimeError, match="Required Wayland globals"):
        wayland_idle.WaylandIdleTracker(timeout_ms=1000)


def test_wayland_idle_tracker_marks_unavailable_on_dispatch_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pywayland(monkeypatch)
    tracker = wayland_idle.WaylandIdleTracker(timeout_ms=1000, select_fn=lambda *_a, **_k: ([], [], []))
    display = _FakeDisplay.instances[-1]
    display.dispatch_error = OSError("dispatch failed")

    assert tracker.is_idle() is None
    assert tracker._available is False


def test_wayland_idle_tracker_marks_unavailable_on_flush_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pywayland(monkeypatch)
    tracker = wayland_idle.WaylandIdleTracker(timeout_ms=1000, select_fn=lambda *_a, **_k: ([], [], []))
    display = _FakeDisplay.instances[-1]
    display.flush_error = RuntimeError("flush failed")

    assert tracker.is_idle() is None
    assert tracker._available is False


def test_create_wayland_idle_tracker_returns_none_on_setup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise OSError("no display")

    monkeypatch.setattr(wayland_idle, "WaylandIdleTracker", boom)
    assert wayland_idle.create_wayland_idle_tracker(timeout_ms=1000) is None


def test_create_notification_handles_destroy_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pywayland(monkeypatch)
    tracker = wayland_idle.WaylandIdleTracker(timeout_ms=1000, select_fn=lambda *_a, **_k: ([], [], []))
    bad = _FakeProxy()

    def bad_destroy() -> None:
        raise RuntimeError("destroy failed")

    bad.destroy = bad_destroy  # type: ignore[method-assign]
    tracker._notification = bad
    tracker._create_notification()
    assert tracker._notification is not None
    assert tracker._notification is not bad
