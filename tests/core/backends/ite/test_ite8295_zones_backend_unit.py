from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8295_zones import protocol
from src.core.backends.ite8295_zones.backend import (
    Ite8295ZonesBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8295_zones.device import Ite8295ZonesKeyboardDevice


def test_protocol_builds_expected_static_report() -> None:
    report = protocol.build_static_report((0x12, 0x34, 0x56), brightness=protocol.RAW_BRIGHTNESS_HIGH)

    assert len(report) == protocol.PACKET_SIZE
    assert report[:20].hex() == "cc16010102123456123456123456123456000000"
    assert report[20:] == bytes(protocol.PACKET_SIZE - 20)


def test_protocol_builds_expected_breathing_report() -> None:
    report = protocol.build_breathing_report(
        ((0x01, 0x02, 0x03), (0x04, 0x05, 0x06), (0x07, 0x08, 0x09), (0x0A, 0x0B, 0x0C)),
        brightness=protocol.RAW_BRIGHTNESS_LOW,
        speed=protocol.RAW_SPEED_MAX,
    )

    assert len(report) == protocol.PACKET_SIZE
    assert report[:20].hex() == "cc160304010102030405060708090a0b0c000000"
    assert report[20:] == bytes(protocol.PACKET_SIZE - 20)


def test_protocol_builds_expected_wave_report_with_left_direction() -> None:
    report = protocol.build_wave_report(brightness=protocol.RAW_BRIGHTNESS_HIGH, speed=3, direction="left")

    assert len(report) == protocol.PACKET_SIZE
    assert report[:20].hex() == "cc16040302ffffffffffffffffffffffff000001"
    assert report[20:] == bytes(protocol.PACKET_SIZE - 20)


def test_protocol_builds_expected_turn_off_report() -> None:
    report = protocol.build_turn_off_report()

    assert len(report) == protocol.PACKET_SIZE
    assert report[:20].hex() == "cc16010101000000000000000000000000000000"
    assert report[20:] == bytes(protocol.PACKET_SIZE - 20)


def test_device_set_color_sends_single_static_report() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)

    device.set_color((0x12, 0x34, 0x56), brightness=50)

    assert sent == [protocol.build_static_report((0x12, 0x34, 0x56), brightness=protocol.RAW_BRIGHTNESS_HIGH)]


def test_device_set_key_colors_accepts_zone_indices() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)

    device.set_key_colors(
        {
            0: (0x11, 0x22, 0x33),
            (0, 1): (0x44, 0x55, 0x66),
            2: (0x77, 0x88, 0x99),
            3: (0xAA, 0xBB, 0xCC),
        },
        brightness=50,
    )

    assert sent == [
        protocol.build_static_report(
            ((0x11, 0x22, 0x33), (0x44, 0x55, 0x66), (0x77, 0x88, 0x99), (0xAA, 0xBB, 0xCC)),
            brightness=protocol.RAW_BRIGHTNESS_HIGH,
        )
    ]


def test_device_set_key_colors_falls_back_to_average_uniform_color() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)

    device.set_key_colors({"esc": (255, 0, 0), "f1": (0, 255, 0), "f2": (0, 0, 255)}, brightness=25)

    assert sent == [protocol.build_static_report((85, 85, 85), brightness=protocol.RAW_BRIGHTNESS_LOW)]


def test_device_turn_off_sends_turn_off_report() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)

    device.turn_off()

    assert sent == [protocol.build_turn_off_report()]
    assert device.is_off() is True
    assert device.get_brightness() == 0


def test_device_set_effect_supports_wave_with_direction() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)

    device.set_effect({"name": "wave", "direction": "left", "brightness": 50, "speed": 6})

    assert sent == [protocol.build_wave_report(brightness=protocol.RAW_BRIGHTNESS_HIGH, speed=3, direction="left")]


def test_device_set_brightness_reapplies_last_effect_state() -> None:
    sent: list[bytes] = []
    device = Ite8295ZonesKeyboardDevice(sent.append)
    device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 50, "speed": 10})

    sent.clear()
    device.set_brightness(25)

    assert sent == [
        protocol.build_breathing_report((0x12, 0x34, 0x56), brightness=protocol.RAW_BRIGHTNESS_LOW, speed=4)
    ]


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8295ZonesBackend()

    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    caps = backend.capabilities()
    assert caps.per_key is False
    assert caps.hardware_effects is True


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


def test_backend_probe_reports_unavailable_when_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    result = Ite8295ZonesBackend().probe()

    assert result.available is False
    assert "disabled" in result.reason.lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8295_zones.backend._find_matching_supported_hidraw_device",
        lambda: None,
    )

    result = Ite8295ZonesBackend().probe()

    assert result.available is False
    assert "lenovo 4-zone" in result.reason.lower()


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC963
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8295)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8295_zones.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8295ZonesBackend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0xc963"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC963
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8295)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8295_zones.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8295ZonesBackend().probe()

    assert result.available is True
    assert result.confidence == 82
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8295_zones.backend.find_matching_hidraw_device", lambda **kwargs: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8295ZonesBackend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "src.core.backends.ite8295_zones.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8295ZonesBackend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr(
        "src.core.backends.ite8295_zones.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8295ZonesBackend().get_device()


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
        "src.core.backends.ite8295_zones.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8295ZonesBackend().get_device()

    assert isinstance(device, Ite8295ZonesKeyboardDevice)
    device.set_effect({"name": "spectrum_cycle", "brightness": 50, "speed": 10})
    assert sent == [protocol.build_smooth_report(brightness=protocol.RAW_BRIGHTNESS_HIGH, speed=4)]


def test_backend_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8295ZonesBackend()

    assert backend.dimensions() == (1, protocol.NUM_ZONES)
    assert set(backend.effects()) == {"breathing", "wave", "spectrum_cycle"}
    assert backend.colors() == {}


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8295ZonesBackend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8295ZonesBackend().is_available() is True