from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import src.core.effects.reactive as reactive_pkg
import src.core.effects.reactive.input as reactive_input
from src.core.effects.reactive.input import close_evdev_keyboards, reactive_synthetic_fallback_enabled
from src.core.effects.reactive.utils import _PressSource
from src.core.resources.layouts import slot_id_for_key_id


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


def test_poll_keypress_slot_id_debug_logs_mapped_input(monkeypatch, caplog) -> None:
    class _InputDevice(_FakeDevice):
        path = "/dev/input/event3"
        name = "AT Translated Set 2 keyboard"

        def read(self):
            return [SimpleNamespace(type=1, value=1, code=30)]

    fake_evdev = SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, KEY={30: "KEY_A"}))
    fake_select = SimpleNamespace(select=lambda readers, _writers, _errors, _timeout: (list(readers), [], []))

    monkeypatch.setenv("KEYRGB_DEBUG_REACTIVE_INPUT", "1")
    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setitem(sys.modules, "select", fake_select)

    with caplog.at_level(logging.INFO, logger=reactive_input.__name__):
        assert reactive_input.poll_keypress_slot_id([_InputDevice()]) == str(slot_id_for_key_id("auto", "a") or "a")

    assert "reactive_input: key_press" in caplog.text
    assert "path=/dev/input/event3" in caplog.text
    assert "key=KEY_A" in caplog.text
    assert "mapped=True" in caplog.text


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


def test_device_debug_name_and_close_helpers() -> None:
    assert reactive_input._device_debug_name(SimpleNamespace()) == "<unknown>"
    assert reactive_input._device_debug_name(SimpleNamespace(name="KB")) == "KB"

    reactive_input._close_evdev_device(SimpleNamespace(), log_key="k", message="m")

    class _BadClose:
        def close(self) -> None:
            raise OSError("gone")

    reactive_input._close_evdev_device(_BadClose(), log_key="k", message="m")

    devices = [_FakeDevice(), _FakeDevice()]
    victim = devices[0]
    reactive_input._drop_evdev_device(devices, victim)
    assert victim not in devices
    assert victim.closed == 1
    reactive_input._drop_evdev_device(devices, _FakeDevice())


def test_read_udev_input_properties_parses_props(tmp_path, monkeypatch) -> None:
    assert reactive_input._read_udev_input_properties(str(tmp_path / "missing")) == {}

    data_file = tmp_path / "c13:64"
    data_file.write_text("E:ID_INPUT_KEYBOARD=1\nE:ID_INPUT_MOUSE=0\nX:ignored\nbad\n", encoding="utf-8")

    class _Stat:
        st_rdev = 123

    real_stat = reactive_input.os.stat

    def fake_stat(path, *args, **kwargs):
        if str(path).endswith("event0"):
            return _Stat()
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(reactive_input.os, "stat", fake_stat)
    monkeypatch.setattr(reactive_input.os, "major", lambda _r: 13)
    monkeypatch.setattr(reactive_input.os, "minor", lambda _r: 64)

    real_path_cls = reactive_input.Path

    class _Path(real_path_cls):  # type: ignore[misc,valid-type]
        def is_file(self) -> bool:  # type: ignore[override]
            if str(self).startswith("/run/udev/data/"):
                return True
            return super().is_file()

        def read_text(self, *args, **kwargs):  # type: ignore[override]
            if str(self).startswith("/run/udev/data/"):
                return data_file.read_text(encoding="utf-8")
            return super().read_text(*args, **kwargs)

    monkeypatch.setattr(reactive_input, "Path", _Path)
    props = reactive_input._read_udev_input_properties(str(tmp_path / "event0"))
    assert props == {"ID_INPUT_KEYBOARD": "1", "ID_INPUT_MOUSE": "0"}
    assert reactive_input._udev_device_is_keyboard(str(tmp_path / "event0")) is True

    monkeypatch.setattr(reactive_input, "_read_udev_input_properties", lambda _p: {})
    assert reactive_input._udev_device_is_keyboard("/dev/x") is None
    monkeypatch.setattr(reactive_input, "_read_udev_input_properties", lambda _p: {"ID_INPUT_KEYBOARD": "0"})
    assert reactive_input._udev_device_is_keyboard("/dev/x") is False


def test_evdev_device_looks_like_keyboard_thresholds(monkeypatch) -> None:
    letter = set(range(10, 30))
    control = set(range(100, 110))
    monkeypatch.setattr(reactive_input, "keyboard_letter_keys", lambda _e: letter)
    monkeypatch.setattr(reactive_input, "keyboard_control_keys", lambda _e: control)
    evdev = SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1))

    class _Dev:
        def __init__(self, keys):
            self._keys = keys

        def capabilities(self, verbose: bool = False):
            return {1: list(self._keys)}

    assert reactive_input._evdev_device_looks_like_keyboard(_Dev(letter | control), evdev) is True
    assert reactive_input._evdev_device_looks_like_keyboard(_Dev(set(range(3))), evdev) is False

    class _Bad:
        def capabilities(self, verbose: bool = False):
            raise OSError("nope")

    assert reactive_input._evdev_device_looks_like_keyboard(_Bad(), evdev) is False


def test_try_open_evdev_disabled_by_env(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_EVDEV", "yes")
    assert reactive_input.try_open_evdev_keyboards() is None


def test_try_open_evdev_returns_none_when_import_missing(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "evdev" or (isinstance(name, str) and name.startswith("evdev")):
            raise ImportError("missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.delenv("KEYRGB_DISABLE_EVDEV", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert reactive_input.try_open_evdev_keyboards() is None


def test_poll_keypress_empty_and_select_idle(monkeypatch) -> None:
    assert reactive_input.poll_keypress_slot_id(None) is None
    assert reactive_input.poll_keypress_slot_id([]) is None

    fake_evdev = SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, KEY={}))
    fake_select = SimpleNamespace(select=lambda *_a, **_k: ([], [], []))
    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setitem(sys.modules, "select", fake_select)
    assert reactive_input.poll_keypress_slot_id([_FakeDevice()]) is None


def test_poll_keypress_select_failure_closes_devices(monkeypatch) -> None:
    class _Dev(_FakeDevice):
        path = "/dev/input/event1"

    fake_evdev = SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, KEY={}))
    fake_select = SimpleNamespace(select=lambda *_a, **_k: (_ for _ in ()).throw(OSError("select fail")))
    monkeypatch.setitem(sys.modules, "evdev", fake_evdev)
    monkeypatch.setitem(sys.modules, "select", fake_select)
    devices = [_Dev()]
    assert reactive_input.poll_keypress_slot_id(devices) is None
    assert devices == []
