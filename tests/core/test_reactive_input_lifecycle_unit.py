from __future__ import annotations

import sys
from types import SimpleNamespace

import src.core.effects.reactive.input as reactive_input
from src.core.effects.reactive.input import close_evdev_keyboards, reactive_synthetic_fallback_enabled
from src.core.effects.reactive.utils import _PressSource


class _FakeDevice:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_close_evdev_keyboards_closes_devices_and_clears_list() -> None:
    devices = [_FakeDevice(), _FakeDevice()]

    close_evdev_keyboards(devices)

    assert devices == []


def test_reactive_synthetic_fallback_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("KEYRGB_REACTIVE_SYNTHETIC_FALLBACK", raising=False)

    assert reactive_synthetic_fallback_enabled() is False

    monkeypatch.setenv("KEYRGB_REACTIVE_SYNTHETIC_FALLBACK", "1")
    assert reactive_synthetic_fallback_enabled() is True


def test_press_source_retries_evdev_open_without_spawning_synthetic(monkeypatch) -> None:
    reopened = [_FakeDevice()]

    monkeypatch.setattr("src.core.effects.reactive.utils.poll_keypress_key_id", lambda _devices: None)
    monkeypatch.setattr("src.core.effects.reactive.utils.try_open_evdev_keyboards", lambda: reopened)

    press = _PressSource(
        devices=[],
        synthetic=True,
        allow_synthetic=False,
        spawn_interval_s=0.01,
        reopen_interval_s=0.05,
    )

    assert press.poll_key_id(dt=0.02) is None
    assert press.devices == []

    assert press.poll_key_id(dt=0.03) is None
    assert press.devices == reopened
    assert press.synthetic is False

    press.close()


def test_try_open_evdev_keyboards_skips_non_keyboard_key_devices(monkeypatch) -> None:
    created: dict[str, _FakeInputDevice] = {}

    class _FakeInputDevice(_FakeDevice):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path
            created[path] = self

        def capabilities(self, verbose: bool = False):
            return {1: []}

    fake_evdev = SimpleNamespace(
        list_devices=lambda: ["/dev/input/event0", "/dev/input/event3", "/dev/input/event4"],
        InputDevice=_FakeInputDevice,
        ecodes=SimpleNamespace(EV_KEY=1),
    )

    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setattr(
        reactive_input,
        "_udev_device_is_keyboard",
        lambda path: {
            "/dev/input/event0": False,
            "/dev/input/event3": True,
            "/dev/input/event4": None,
        }[path],
    )
    monkeypatch.setattr(
        reactive_input,
        "_evdev_device_looks_like_keyboard",
        lambda dev, _evdev: dev.path == "/dev/input/event4",
    )

    devices = reactive_input.try_open_evdev_keyboards()

    assert devices is not None
    assert [dev.path for dev in devices] == ["/dev/input/event3", "/dev/input/event4"]
    assert "/dev/input/event0" not in created


def test_try_open_evdev_keyboards_closes_unknown_non_keyboards(monkeypatch) -> None:
    created: dict[str, _FakeInputDevice] = {}

    class _FakeInputDevice(_FakeDevice):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path
            created[path] = self

        def capabilities(self, verbose: bool = False):
            return {1: []}

    fake_evdev = SimpleNamespace(
        list_devices=lambda: ["/dev/input/event5"],
        InputDevice=_FakeInputDevice,
        ecodes=SimpleNamespace(EV_KEY=1),
    )

    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setattr(reactive_input, "_udev_device_is_keyboard", lambda _path: None)
    monkeypatch.setattr(reactive_input, "_evdev_device_looks_like_keyboard", lambda _dev, _evdev: False)

    devices = reactive_input.try_open_evdev_keyboards()

    assert devices is None
    assert created["/dev/input/event5"].closed == 1
