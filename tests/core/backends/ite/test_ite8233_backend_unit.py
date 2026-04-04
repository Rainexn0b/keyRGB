from __future__ import annotations

import os

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.ite8233 import backend as ite8233_backend_module
from src.core.backends.ite8233.backend import (
    Ite8233Backend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8233.device import Ite8233LightbarDevice
from src.core.backends.ite8233 import protocol as ite8233_protocol


def test_ite8233_backend_metadata_is_research_backed_experimental() -> None:
    backend = Ite8233Backend()

    assert backend.name == "ite8233"
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
    assert probe.identifiers["usb_pid"] == "0x7001"


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
    assert info.product_id == ite8233_protocol.SUPPORTED_PRODUCT_IDS[0]
    assert info.hid_id == "forced:048d:7001"


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
        "src.core.backends.ite8233.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
    )

    result = Ite8233Backend().probe()

    assert result.available is True
    assert result.confidence == 83
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_ite8233_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8233Backend().get_device()


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8233.backend._find_matching_supported_hidraw_device", lambda: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_ite8233_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "src.core.backends.ite8233.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err)
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8233Backend().get_device()


def test_ite8233_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = RuntimeError("transport failed")
    monkeypatch.setattr(
        "src.core.backends.ite8233.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err)
    )

    with pytest.raises(BackendIOError, match="transport failed"):
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

    monkeypatch.setattr(
        "src.core.backends.ite8233.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8233Backend().get_device()

    assert isinstance(device, Ite8233LightbarDevice)
    device.set_color((0x12, 0x34, 0x56), brightness=50)
    assert seen[-2] == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8233Backend()

    assert backend.dimensions() == (1, 1)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_ite8233_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8233Backend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8233Backend().is_available() is True


def test_ite8233_protocol_builds_expected_uniform_color_report() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56))

    assert report == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_brightness_report() -> None:
    report = ite8233_protocol.build_brightness_report(37)

    assert report == bytes((0x08, 0x22, 0x01, 0x01, 37, 0x01, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_off_sequence() -> None:
    reports = ite8233_protocol.build_turn_off_reports()

    assert reports == (
        bytes((0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x1A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    )


def test_ite8233_device_sends_color_and_brightness_reports() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report))

    device.set_color((0x20, 0x40, 0x60), brightness=25)

    assert seen == [
        bytes((0x14, 0x00, 0x01, 0x10, 0x20, 0x30, 0x00, 0x00)),
        bytes((0x08, 0x22, 0x01, 0x01, 50, 0x01, 0x00, 0x00)),
    ]
    assert device.is_off() is False
    assert device.get_brightness() == 25


def test_ite8233_device_turn_off_sends_full_off_sequence() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report))

    device.turn_off()

    assert seen == list(ite8233_protocol.build_turn_off_reports())
    assert device.is_off() is True
    assert device.get_brightness() == 0
