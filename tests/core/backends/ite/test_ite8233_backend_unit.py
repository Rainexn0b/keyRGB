from __future__ import annotations

import os

import pytest

from keyrgb.core.backends.base import BackendStability, ExperimentalEvidence
from keyrgb.core.backends.exceptions import BackendIOError
from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo import (
    backend as ite8233_backend_module,
    protocol as ite8233_protocol,
)
from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend import (
    Ite8233Backend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.device import Ite8233LightbarDevice


def test_ite8233_backend_metadata_is_research_backed_experimental() -> None:
    backend = Ite8233Backend()

    assert backend.name == "ite8233_none_chassis_lightbar_clevo"
    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    assert backend.capabilities().color is True
    assert backend.capabilities().per_key is False


def test_ite8233_probe_reports_detected_device_but_requires_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    hidraw_path = tmp_path / "hidraw-test"
    hidraw_path.write_bytes(b"")

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setenv("KEYRGB_ITE8233_HIDRAW_PATH", os.fspath(hidraw_path))

    probe = Ite8233Backend().probe()

    assert probe.available is False
    assert "experimental backend disabled" in probe.reason.lower()
    assert probe.identifiers["usb_vid"] == "0x048d"
    assert probe.identifiers["usb_pid"] == "0x7001"
    assert probe.identifiers["hidraw"] == os.fspath(hidraw_path)


def test_ite8233_probe_reports_missing_device_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ITE8233_HIDRAW_PATH", raising=False)
    monkeypatch.setattr(ite8233_backend_module, "find_matching_hidraw_device", lambda vendor_id, product_id: None)

    probe = Ite8233Backend().probe()

    assert probe.available is False
    assert "no matching hidraw device" in probe.reason
    assert probe.identifiers["usb_vid"] == "0x048d"
    assert probe.identifiers["usb_pid"] == "0x6010/0x7000/0x7001"


def test_find_matching_supported_hidraw_device_uses_forced_existing_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    forced = tmp_path / "hidraw9"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv(ite8233_protocol.HIDRAW_PATH_ENV, str(forced))

    info = _find_matching_supported_hidraw_device()

    assert info is not None
    assert info.devnode == forced
    assert info.vendor_id == ite8233_protocol.VENDOR_ID
    assert info.product_id == ite8233_protocol.DEFAULT_PRODUCT_ID
    assert info.hid_id == f"forced:{ite8233_protocol.VENDOR_ID:04x}:{ite8233_protocol.DEFAULT_PRODUCT_ID:04x}"


def test_ite8233_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x7001
        devnode = "/dev/hidraw7"
        hid_name = "ITE Device(8233)"
        hid_id = "0003:048D:7001"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8233Backend().probe()

    assert result.available is True
    assert result.confidence == 83
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_ite8233_probe_reports_vendor_lightbar_7000_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x7000
        devnode = "/dev/hidraw8"
        hid_name = "ITE Lightbar"
        hid_id = "0003:048D:7000"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8233Backend().probe()

    assert result.available is True
    assert result.identifiers["usb_pid"] == "0x7000"
    assert result.identifiers["hidraw"] == "/dev/hidraw8"


def test_ite8233_probe_reports_vendor_lightbar_6010_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x6010
        devnode = "/dev/hidraw6"
        hid_name = "ITE Lightbar"
        hid_id = "0003:048D:6010"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8233Backend().probe()

    assert result.available is True
    assert result.identifiers["usb_pid"] == "0x6010"
    assert result.identifiers["hidraw"] == "/dev/hidraw6"


def test_ite8233_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8233Backend().get_device()


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._find_matching_supported_hidraw_device",
        lambda: None,
    )

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_ite8233_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8233Backend().get_device()


def test_ite8233_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = RuntimeError("transport failed")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8233Backend().get_device()


def test_ite8233_get_device_propagates_unexpected_open_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = AssertionError("unexpected transport bug")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(AssertionError, match="unexpected transport bug"):
        Ite8233Backend().get_device()


def test_ite8233_get_device_returns_lightbar_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    seen: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            seen.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = "/dev/hidraw7"
        product_id = 0x7000

    monkeypatch.setattr(
        "keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8233Backend().get_device()

    assert isinstance(device, Ite8233LightbarDevice)
    device.set_color((0x12, 0x34, 0x56), brightness=50)
    assert seen[-2] == bytes((0x14, 0x01, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8233Backend()

    assert backend.dimensions() == (1, 1)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_ite8233_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8233Backend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8233Backend().is_available() is True
