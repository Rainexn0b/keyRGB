from __future__ import annotations

import sys
import types

import pytest

from src.core.diagnostics import snapshots


class _MissingNode:
    def exists(self) -> bool:
        return False


class _GoodLedNode:
    def __init__(self, name: str) -> None:
        self.name = name

    def is_dir(self) -> bool:
        return True

    def __truediv__(self, _: str) -> _MissingNode:
        return _MissingNode()

    def __str__(self) -> str:
        return f"/fake/{self.name}"


class _BrokenLedNode(_GoodLedNode):
    def is_dir(self) -> bool:
        raise OSError("cannot inspect led")


class _FakeLedsRoot:
    def exists(self) -> bool:
        return True

    def iterdir(self) -> list[_GoodLedNode]:
        return [_GoodLedNode("aaa::kbd_backlight"), _BrokenLedNode("zzz::other")]


def test_sysfs_leds_snapshot_keeps_partial_results_when_led_enumeration_breaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshots, "sysfs_leds_root", lambda: _FakeLedsRoot())

    all_leds, leds = snapshots.sysfs_leds_snapshot()

    assert all_leds == [{"name": "aaa::kbd_backlight", "path": "/fake/aaa::kbd_backlight"}]
    assert leds == [{"name": "aaa::kbd_backlight", "path": "/fake/aaa::kbd_backlight"}]


def test_usb_ids_snapshot_skips_devices_with_bad_identifier_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    class FakeDevice:
        def __init__(self, vid: object, pid: object) -> None:
            self.idVendor = vid
            self.idProduct = pid

    fake_usb = types.ModuleType("usb")
    fake_usb_core = types.ModuleType("usb.core")
    fake_usb.core = fake_usb_core
    fake_usb_core.find = lambda *, find_all: [
        FakeDevice(0x048D, 0xCE00),
        FakeDevice("bad", 0xCE00),
        FakeDevice(0x048D, 0xCE00),
    ]

    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", fake_usb_core)

    assert snapshots.usb_ids_snapshot(include_usb=True) == ["048d:ce00"]


def test_usb_ids_snapshot_tolerates_pyusb_scan_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    class FakeUsbError(OSError):
        pass

    fake_usb = types.ModuleType("usb")
    fake_usb_core = types.ModuleType("usb.core")
    fake_usb.core = fake_usb_core
    fake_usb_core.USBError = FakeUsbError

    def boom(*, find_all: bool) -> list[object]:
        raise FakeUsbError(f"scan failed: {find_all}")

    fake_usb_core.find = boom

    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", fake_usb_core)

    assert snapshots.usb_ids_snapshot(include_usb=True) == []


def test_process_snapshot_keeps_identity_fields_when_groups_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshots.os, "getpid", lambda: 123)
    monkeypatch.setattr(snapshots.os, "geteuid", lambda: 456)
    monkeypatch.setattr(snapshots.os, "getegid", lambda: 789)
    monkeypatch.setattr(snapshots.os, "getgroups", lambda: (_ for _ in ()).throw(OSError("groups failed")))

    assert snapshots.process_snapshot() == {"pid": 123, "euid": 456, "egid": 789}
