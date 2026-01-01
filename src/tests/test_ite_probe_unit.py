from __future__ import annotations

import sys
import types

import pytest

from src.core.backends.ite import Ite8291r3Backend


def test_ite_probe_uses_declared_product_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    # Fake ite8291r3_ctl.ite8291r3 module
    fake_ite = types.SimpleNamespace(VENDOR_ID=0x048D, PRODUCT_IDS=[0x600B, 0xCE00])
    fake_pkg = types.SimpleNamespace(ite8291r3=fake_ite)
    monkeypatch.setitem(sys.modules, "ite8291r3_ctl", fake_pkg)

    # Fake usb.core.find: only CE00 is present
    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            if idVendor == 0x048D and idProduct == 0xCE00:
                return object()
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is True
    assert res.confidence == 90
    assert res.identifiers["usb_vid"] == "0x048d"
    assert res.identifiers["usb_pid"] == "0xce00"


def test_ite_probe_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    fake_ite = types.SimpleNamespace(VENDOR_ID=0x048D, PRODUCT_IDS=[0x600B])
    fake_pkg = types.SimpleNamespace(ite8291r3=fake_ite)
    monkeypatch.setitem(sys.modules, "ite8291r3_ctl", fake_pkg)

    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is False
    assert res.confidence == 0


def test_ite_probe_low_confidence_when_usb_scan_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ite = types.SimpleNamespace(VENDOR_ID=0x048D, PRODUCT_IDS=[0x600B])
    fake_pkg = types.SimpleNamespace(ite8291r3=fake_ite)
    monkeypatch.setitem(sys.modules, "ite8291r3_ctl", fake_pkg)

    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is True
    assert res.confidence == 60
