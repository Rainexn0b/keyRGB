from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.ite8297 import protocol
from src.core.backends.ite8297.backend import (
    Ite8297Backend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8297.device import Ite8297KeyboardDevice
from src.core.backends.base import BackendStability, ExperimentalEvidence


def test_protocol_builds_64_byte_uniform_color_report() -> None:
    report = protocol.build_uniform_color_report((0x12, 0x34, 0x56))

    assert len(report) == 64
    assert report[:7].hex() == "ccb00101123456"
    assert report[7:] == bytes(57)


def test_device_scales_color_by_brightness() -> None:
    sent: list[bytes] = []
    device = Ite8297KeyboardDevice(sent.append)

    device.set_color((100, 50, 25), brightness=25)

    assert sent[-1][:7].hex() == "ccb0010132190c"


def test_device_set_key_colors_falls_back_to_average_uniform_color() -> None:
    sent: list[bytes] = []
    device = Ite8297KeyboardDevice(sent.append)

    device.set_key_colors(
        {
            "esc": (255, 0, 0),
            "f1": (0, 255, 0),
            "f2": (0, 0, 255),
        },
        brightness=50,
    )

    assert sent[-1][:7].hex() == "ccb00101555555"


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8297Backend()

    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    assert backend.capabilities().color is True
    assert backend.capabilities().per_key is False


def test_find_matching_supported_hidraw_device_uses_forced_existing_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forced = tmp_path / "hidraw9"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv(protocol.HIDRAW_PATH_ENV, str(forced))

    info = _find_matching_supported_hidraw_device()

    assert info is not None
    assert info.devnode == forced
    assert info.vendor_id == protocol.VENDOR_ID
    assert info.product_id == protocol.SUPPORTED_PRODUCT_IDS[0]
    assert info.hid_id == "forced:048d:8297"


def test_backend_probe_reports_unavailable_when_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    result = Ite8297Backend().probe()

    assert result.available is False
    assert result.confidence == 0
    assert "disabled" in (result.reason or "").lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr("src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: None)

    result = Ite8297Backend().probe()

    assert result.available is False
    assert result.confidence == 0
    assert result.reason == "no matching hidraw device"


def test_find_matching_supported_hidraw_device_falls_back_to_scanned_match_when_forced_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_match = object()
    monkeypatch.setenv(protocol.HIDRAW_PATH_ENV, "/tmp/does-not-exist")
    monkeypatch.setattr("src.core.backends.ite8297.backend.find_matching_hidraw_device", lambda *_a, **_k: dummy_match)

    assert _find_matching_supported_hidraw_device() is dummy_match


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x8297
        devnode = "/dev/hidraw7"
        hid_name = "ITE 8297"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
    )

    result = Ite8297Backend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0x8297"


def test_backend_probe_reports_available_when_opted_in(monkeypatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x8297
        devnode = "/dev/hidraw7"
        hid_name = "ITE 8297"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
    )

    result = Ite8297Backend().probe()

    assert result.available is True
    assert result.confidence == 84
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8297Backend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = PermissionError("permission denied")
    monkeypatch.setattr("src.core.backends.ite8297.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8297Backend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = RuntimeError("transport failed")
    monkeypatch.setattr("src.core.backends.ite8297.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(RuntimeError, match="transport failed"):
        Ite8297Backend().get_device()


def test_backend_get_device_returns_keyboard_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = Path("/dev/hidraw7")

    monkeypatch.setattr(
        "src.core.backends.ite8297.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8297Backend().get_device()

    assert isinstance(device, Ite8297KeyboardDevice)
    device.set_color((0x12, 0x34, 0x56), brightness=50)
    assert sent[-1][:7].hex() == "ccb00101123456"


def test_backend_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8297Backend()

    assert backend.dimensions() == (1, 1)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8297Backend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8297Backend().is_available() is True
