from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from src.tray.pollers.idle_power import _source_probe
from src.tray.pollers.idle_power import _wayland_idle
from src.tray.pollers.idle_power import _input_idle


class _FakeWaylandTracker:
    def __init__(self, *, works: bool = True) -> None:
        self.works = works
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeInputTracker:
    def __init__(self, *, idle: float | None = 0.0) -> None:
        self.idle = idle
        self.closed = False

    def seconds_since_activity(self) -> float | None:
        return self.idle

    def close(self) -> None:
        self.closed = True


def test_detect_idle_power_source_prefers_wayland_on_wayland_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")

    tracker = _FakeWaylandTracker()
    monkeypatch.setattr(
        _wayland_idle,
        "create_wayland_idle_tracker",
        lambda **kwargs: tracker if kwargs.get("timeout_ms") == 1000 else None,
    )
    monkeypatch.setattr(_input_idle, "InputIdleTracker", lambda: _FakeInputTracker())

    result = _source_probe.detect_idle_power_source()

    assert result == "Wayland compositor idle"
    assert tracker.closed


def test_detect_idle_power_source_falls_back_to_evdev_when_wayland_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_SOCKET", raising=False)

    monkeypatch.setattr(_input_idle, "InputIdleTracker", lambda: _FakeInputTracker(idle=1.2))

    result = _source_probe.detect_idle_power_source()

    assert result == "evdev input devices"


def test_detect_idle_power_source_falls_back_to_heuristic_when_no_input_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_SOCKET", raising=False)

    monkeypatch.setattr(_input_idle, "InputIdleTracker", lambda: _FakeInputTracker(idle=None))

    result = _source_probe.detect_idle_power_source()

    assert result == "system idle / brightness heuristic"


def test_detect_idle_power_source_falls_back_when_wayland_tracker_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")

    monkeypatch.setattr(_wayland_idle, "create_wayland_idle_tracker", lambda **kwargs: None)
    monkeypatch.setattr(_input_idle, "InputIdleTracker", lambda: _FakeInputTracker(idle=0.5))

    result = _source_probe.detect_idle_power_source()

    assert result == "evdev input devices"


def test_detect_idle_power_source_survives_wayland_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")

    def raise_import(**kwargs):
        raise ImportError("no pywayland")

    monkeypatch.setattr(_wayland_idle, "create_wayland_idle_tracker", raise_import)
    monkeypatch.setattr(_input_idle, "InputIdleTracker", lambda: _FakeInputTracker(idle=0.5))

    result = _source_probe.detect_idle_power_source()

    assert result == "evdev input devices"


def test_format_idle_power_source_returns_label_or_unknown() -> None:
    assert _source_probe.format_idle_power_source("Wayland compositor idle") == "Wayland compositor idle"
    assert _source_probe.format_idle_power_source("") == "Unknown"
    assert _source_probe.format_idle_power_source(None) == "Unknown"
