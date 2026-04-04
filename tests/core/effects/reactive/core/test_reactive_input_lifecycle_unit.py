from __future__ import annotations

import sys
from types import SimpleNamespace

import src.core.effects.reactive as reactive_pkg
import src.core.effects.reactive.input as reactive_input
from src.core.resources.layouts import slot_id_for_key_id
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

    monkeypatch.setattr("src.core.effects.reactive.utils.poll_keypress_slot_id", lambda _devices: None)
    monkeypatch.setattr("src.core.effects.reactive.utils.try_open_evdev_keyboards", lambda: reopened)

    press = _PressSource(
        devices=[],
        synthetic=True,
        allow_synthetic=False,
        spawn_interval_s=0.01,
        reopen_interval_s=0.05,
    )

    assert press.poll_slot_id(dt=0.02) is None
    assert press.devices == []

    assert press.poll_slot_id(dt=0.03) is None
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


def test_load_active_profile_keymap_logs_failures_and_returns_empty_map(monkeypatch) -> None:
    import src.core.profile as profile_pkg

    logs: list[tuple[tuple[object, ...], dict[str, object]]] = []
    fake_profiles = SimpleNamespace(
        get_active_profile=lambda: "default",
        load_keymap=lambda _active: (_ for _ in ()).throw(OSError("boom")),
    )

    monkeypatch.setattr(profile_pkg, "profiles", fake_profiles, raising=False)
    monkeypatch.setattr(reactive_input, "log_throttled", lambda *args, **kwargs: logs.append((args, kwargs)))

    assert reactive_input.load_active_profile_slot_keymap() == {}
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "effects.reactive.profile_keymap_load_failed"
    assert kwargs["exc"].args == ("boom",)


def test_load_active_profile_keymap_normalizes_single_and_multi_cell_entries(monkeypatch) -> None:
    import src.core.profile as profile_pkg

    fake_profiles = SimpleNamespace(
        get_active_profile=lambda: "default",
        load_keymap=lambda _active: {
            "A": (0, 0),
            "ENTER": ((1, 2), (1, 3)),
            "ESC": "0,1",
        },
    )

    monkeypatch.setattr(profile_pkg, "profiles", fake_profiles, raising=False)

    assert reactive_input.load_active_profile_slot_keymap() == {
        str(slot_id_for_key_id("auto", "a") or "a"): ((0, 0),),
        str(slot_id_for_key_id("auto", "enter") or "enter"): ((1, 2), (1, 3)),
        str(slot_id_for_key_id("auto", "esc") or "esc"): ((0, 1),),
    }


def test_evdev_key_name_to_slot_id_uses_physical_slot_identity() -> None:
    assert reactive_input.evdev_key_name_to_slot_id("KEY_A") == str(slot_id_for_key_id("auto", "a") or "a")
    assert reactive_input.evdev_key_name_to_slot_id("KEY_ENTER") == str(slot_id_for_key_id("auto", "enter") or "enter")


def test_poll_keypress_slot_id_logs_and_drops_devices_on_read_failure(monkeypatch) -> None:
    logs: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _BrokenInputDevice(_FakeDevice):
        path = "/dev/input/event9"

        def read(self):
            raise OSError("read failed")

    device = _BrokenInputDevice()
    fake_evdev = SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, KEY={}))
    fake_select = SimpleNamespace(select=lambda readers, _writers, _errors, _timeout: (list(readers), [], []))

    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setitem(sys.modules, "select", fake_select)
    monkeypatch.setattr(reactive_input, "log_throttled", lambda *args, **kwargs: logs.append((args, kwargs)))

    devices = [device]

    assert reactive_input.poll_keypress_slot_id(devices) is None
    assert devices == []
    assert device.closed == 1
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "effects.reactive.evdev.read_failed"
    assert kwargs["exc"].args == ("read failed",)


def test_reactive_input_module_exposes_only_slot_first_loader_and_poller_names() -> None:
    assert hasattr(reactive_input, "load_active_profile_slot_keymap")
    assert hasattr(reactive_input, "poll_keypress_slot_id")
    assert not hasattr(reactive_input, "load_active_profile_keymap")
    assert not hasattr(reactive_input, "poll_keypress_key_id")


def test_reactive_package_exports_only_slot_first_loader_and_poller_names() -> None:
    assert "load_active_profile_slot_keymap" in reactive_pkg.__all__
    assert "poll_keypress_slot_id" in reactive_pkg.__all__
    assert "load_active_profile_keymap" not in reactive_pkg.__all__
    assert "poll_keypress_key_id" not in reactive_pkg.__all__
