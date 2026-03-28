from __future__ import annotations

from src.core.backends.ite8297 import protocol
from src.core.backends.ite8297.backend import Ite8297Backend
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


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x8297
        devnode = "/dev/hidraw7"
        hid_name = "ITE 8297"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr("src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

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
    monkeypatch.setattr("src.core.backends.ite8297.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8297Backend().probe()

    assert result.available is True
    assert result.confidence == 84
    assert result.identifiers["hidraw"] == "/dev/hidraw7"