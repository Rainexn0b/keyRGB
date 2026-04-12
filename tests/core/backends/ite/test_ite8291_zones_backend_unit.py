from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8291_zones import protocol
from src.core.backends.ite8291_zones.backend import (
    Ite8291ZonesBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8291_zones.device import Ite8291ZonesKeyboardDevice


def test_protocol_builds_expected_zone_enable_report() -> None:
    assert protocol.build_zone_enable_report() == bytes.fromhex("1a00010400000001")


def test_protocol_builds_expected_zone_color_report() -> None:
    assert protocol.build_zone_color_report(1, (0x12, 0x34, 0x56)) == bytes.fromhex("1400021234560000")


def test_protocol_builds_expected_commit_state_report() -> None:
    assert protocol.build_commit_state_report(25) == bytes.fromhex("0802010319080000")


def test_protocol_builds_expected_turn_off_sequence() -> None:
    assert list(protocol.build_turn_off_reports()) == [
        bytes.fromhex("0902000000000000"),
        bytes.fromhex("1200030000000000"),
        bytes.fromhex("0805000000000000"),
        bytes.fromhex("0801000000000000"),
        bytes.fromhex("1a00000000000001"),
    ]


def test_device_set_color_writes_enable_zone_colors_and_commit() -> None:
    sent: list[bytes] = []
    device = Ite8291ZonesKeyboardDevice(sent.append)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0] == protocol.build_zone_enable_report()
    assert sent[1:5] == [protocol.build_zone_color_report(zone, (0x12, 0x34, 0x56)) for zone in range(protocol.NUM_ZONES)]
    assert sent[5] == protocol.build_commit_state_report(25)


def test_device_set_key_colors_falls_back_to_average_uniform_color() -> None:
    sent: list[bytes] = []
    device = Ite8291ZonesKeyboardDevice(sent.append)

    device.set_key_colors(
        {
            "esc": (255, 0, 0),
            "f1": (0, 255, 0),
            "f2": (0, 0, 255),
        },
        brightness=50,
    )

    assert sent[1:5] == [protocol.build_zone_color_report(zone, (85, 85, 85)) for zone in range(protocol.NUM_ZONES)]


def test_device_turn_off_sends_full_sequence() -> None:
    sent: list[bytes] = []
    device = Ite8291ZonesKeyboardDevice(sent.append)

    device.turn_off()

    assert sent == list(protocol.build_turn_off_reports())
    assert device.is_off() is True


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8291ZonesBackend()

    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    assert backend.capabilities().per_key is False
    assert backend.capabilities().color is True


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
    assert info.product_id == protocol.PRODUCT_ID
    assert info.bcd_device == protocol.REQUIRED_BCD_DEVICE


def test_backend_probe_reports_unavailable_when_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    result = Ite8291ZonesBackend().probe()

    assert result.available is False
    assert "disabled" in (result.reason or "").lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr("src.core.backends.ite8291_zones.backend._find_matching_supported_hidraw_device", lambda: None)

    result = Ite8291ZonesBackend().probe()

    assert result.available is False
    assert "4-zone firmware" in result.reason.lower()


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xCE00
        bcd_device = 0x0002
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8291)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr("src.core.backends.ite8291_zones.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8291ZonesBackend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_bcd_device"] == "0x0002"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xCE00
        bcd_device = 0x0002
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8291)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr("src.core.backends.ite8291_zones.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8291ZonesBackend().probe()

    assert result.available is True
    assert result.confidence == 80
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_open_matching_transport_raises_when_bcd_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTransport:
        closed = False

        def close(self) -> None:
            self.closed = True

    class DummyInfo:
        bcd_device = 0x0003

    transport = DummyTransport()
    monkeypatch.setattr(
        "src.core.backends.ite8291_zones.backend.open_matching_hidraw_transport",
        lambda **kwargs: (transport, DummyInfo()),
    )

    with pytest.raises(RuntimeError, match="not the supported 4-zone"):
        _open_matching_transport()
    assert transport.closed is True


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8291ZonesBackend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr("src.core.backends.ite8291_zones.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8291ZonesBackend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr("src.core.backends.ite8291_zones.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8291ZonesBackend().get_device()


def test_backend_get_device_propagates_unexpected_open_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8291_zones.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected transport bug")),
    )

    with pytest.raises(AssertionError, match="unexpected transport bug"):
        Ite8291ZonesBackend().get_device()


def test_backend_get_device_returns_zone_keyboard_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = Path("/dev/hidraw7")

    monkeypatch.setattr(
        "src.core.backends.ite8291_zones.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8291ZonesBackend().get_device()

    assert isinstance(device, Ite8291ZonesKeyboardDevice)
    device.set_color((0x12, 0x34, 0x56), brightness=25)
    assert sent[0] == protocol.build_zone_enable_report()
    assert sent[-1] == protocol.build_commit_state_report(25)


def test_backend_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8291ZonesBackend()

    assert backend.dimensions() == (1, protocol.NUM_ZONES)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8291ZonesBackend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8291ZonesBackend().is_available() is True