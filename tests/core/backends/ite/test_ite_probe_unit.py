from __future__ import annotations

import sys
import types

import pytest

from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8291r3 import Ite8291r3Backend


def test_ite_probe_uses_declared_product_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

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


def test_ite_probe_unavailable_when_no_matching_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

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


def test_ite_probe_low_confidence_when_usb_scan_runtime_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    class FakeUsbError(OSError):
        pass

    class FakeUsbCore:
        USBError = FakeUsbError

        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            raise FakeUsbError(f"scan failed for 0x{idVendor:04x}:0x{idProduct:04x}")

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    res = Ite8291r3Backend().probe()
    assert res.available is True
    assert res.confidence == 60
    assert "usb scan unavailable" in (res.reason or "")


def test_ite_probe_low_confidence_when_usb_scan_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is True
    assert res.confidence == 60


def test_ite_probe_detects_ite8297_as_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

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


def test_ite_probe_rejects_known_ce00_zone_only_firmware_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            if idVendor == 0x048D and idProduct == 0xCE00:
                return types.SimpleNamespace(bcdDevice=0x0002)
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    backend = Ite8291r3Backend()
    res = backend.probe()
    assert res.available is False
    assert res.confidence == 0
    assert "zone-only" in (res.reason or "").lower()
    assert res.identifiers["usb_vid"] == "0x048d"
    assert res.identifiers["usb_pid"] == "0xce00"
    assert res.identifiers["usb_bcd_device"] == "0x0002"


def test_ite_probe_rejects_unexpected_non_r3_firmware_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)

    class FakeUsbCore:
        @staticmethod
        def find(*, idVendor: int, idProduct: int):
            if idVendor == 0x048D and idProduct == 0x6004:
                return types.SimpleNamespace(bcdDevice=0x0004)
            return None

    fake_usb = types.SimpleNamespace(core=FakeUsbCore)
    monkeypatch.setitem(sys.modules, "usb", fake_usb)
    monkeypatch.setitem(sys.modules, "usb.core", FakeUsbCore)

    res = Ite8291r3Backend().probe()
    assert res.available is False
    assert "unexpected firmware revision" in (res.reason or "").lower()
    assert res.identifiers["usb_bcd_device"] == "0x0004"


def test_ite_probe_denylists_known_other_protocol_families() -> None:
    from src.core.backends.ite8291r3 import backend as ite_backend

    deny = list(getattr(ite_backend, "_KNOWN_UNSUPPORTED_USB_IDS", []) or [])
    assert (0x048D, 0x8297) in deny
    assert (0x048D, 0x5702) in deny
    assert (0x048D, 0xC966) in deny


def test_ite_probe_supported_usb_ids_cover_known_r3_devices() -> None:
    """Lock in KeyRGB's native ite8291r3 USB ID set."""

    from src.core.backends.ite8291r3 import backend as ite_backend

    allow = set(getattr(ite_backend, "_SUPPORTED_USB_IDS", []) or [])

    # Native ite8291r3 uses the rev-0.03 vendor-confirmed PID set.
    assert (0x048D, 0x6004) in allow
    assert (0x048D, 0x6006) in allow
    assert (0x048D, 0x600B) in allow
    assert (0x048D, 0xCE00) in allow


def test_ite_backend_get_device_tags_speed_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTransport:
        def send_control_report(self, report: bytes) -> int:
            return len(report)

        def read_control_report(self, length: int) -> bytes:
            return bytes(length)

        def write_data(self, payload: bytes) -> int:
            return len(payload)

    backend = Ite8291r3Backend()
    monkeypatch.setattr(backend, "_open_matching_transport", lambda: (DummyTransport(), object()))

    kb = backend.get_device()

    assert kb.keyrgb_hw_speed_policy == "inverted"
    assert kb.keyrgb_per_key_mode_policy == "reassert_every_frame"


def test_ite_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    err = PermissionError("permission denied")

    backend = Ite8291r3Backend()
    monkeypatch.setattr(backend, "_open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(PermissionError, match="udev rule"):
        backend.get_device()


def test_ite_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    err = RuntimeError("transport failed")

    backend = Ite8291r3Backend()
    monkeypatch.setattr(backend, "_open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(BackendIOError, match="transport failed"):
        backend.get_device()


def test_ite_backend_is_available_returns_false_when_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = Ite8291r3Backend()
    monkeypatch.setattr(backend, "_load_usb_core", lambda: (_ for _ in ()).throw(ImportError("missing usb module")))

    assert backend.is_available() is False
