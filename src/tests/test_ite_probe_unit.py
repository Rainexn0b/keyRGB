from __future__ import annotations

import sys
import types

import pytest

from src.core.backends.ite8291r3 import Ite8291r3Backend


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


def test_ite_probe_detects_ite8297_as_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    fake_ite = types.SimpleNamespace(VENDOR_ID=0x048D, PRODUCT_IDS=[0x600B])
    fake_pkg = types.SimpleNamespace(ite8291r3=fake_ite)
    monkeypatch.setitem(sys.modules, "ite8291r3_ctl", fake_pkg)

    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            if idVendor == 0x048D and idProduct == 0x8297:
                return object()
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is False
    assert res.confidence == 0
    assert "unsupported" in (res.reason or "").lower()
    assert res.identifiers["usb_vid"] == "0x048d"
    assert res.identifiers["usb_pid"] == "0x8297"


def test_ite_probe_uses_keyrgb_fallback_product_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even if ite8291r3_ctl is older, KeyRGB should still probe known devices."""

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    # Simulate an ite8291r3_ctl version that only knows about 0x600B.
    fake_ite = types.SimpleNamespace(VENDOR_ID=0x048D, PRODUCT_IDS=[0x600B])
    fake_pkg = types.SimpleNamespace(ite8291r3=fake_ite)
    monkeypatch.setitem(sys.modules, "ite8291r3_ctl", fake_pkg)

    # Pretend only 0x6008 exists on the system. This should still be detected
    # thanks to KeyRGB's fallback USB ID list.
    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            if idVendor == 0x048D and idProduct == 0x6008:
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
    assert res.identifiers["usb_pid"] == "0x6008"


def test_ite_probe_denylists_known_other_protocol_families() -> None:
    from src.core.backends.ite8291r3 import backend as ite_backend

    deny = list(getattr(ite_backend, "_KNOWN_UNSUPPORTED_USB_IDS", []) or [])
    assert (0x048D, 0x8297) in deny
    assert (0x048D, 0x5702) in deny
    assert (0x048D, 0xC966) in deny


def test_ite_probe_fallback_usb_ids_cover_known_devices() -> None:
    """Lock in KeyRGB's own fallback USB IDs.

    This test is intentionally independent of upstream `ite8291r3_ctl` drift.
    """

    from src.core.backends.ite8291r3 import backend as ite_backend

    allow = set(getattr(ite_backend, "_FALLBACK_USB_IDS", []) or [])

    # Known ITE 8291r3 family IDs (includes Wootbook 0x600B) + generic 0x6008.
    assert (0x048D, 0x6004) in allow
    assert (0x048D, 0x6006) in allow
    assert (0x048D, 0x6008) in allow
    assert (0x048D, 0x600B) in allow
    assert (0x048D, 0xCE00) in allow

