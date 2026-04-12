from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8291 import protocol
from src.core.backends.ite8291.backend import (
    Ite8291Backend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8291.device import Ite8291KeyboardDevice


def test_protocol_builds_expected_user_mode_report() -> None:
    assert protocol.build_user_mode_report(25) == bytes.fromhex("0802330019000000")


def test_protocol_builds_expected_row_announce_report() -> None:
    assert protocol.build_row_announce_report(2) == bytes.fromhex("1600020000000000")


def test_protocol_builds_row_data_with_two_byte_padding_and_bgr_planes() -> None:
    row = [(0, 0, 0) for _ in range(protocol.NUM_COLS)]
    row[0] = (0x12, 0x34, 0x56)
    row[-1] = (0xAA, 0xBB, 0xCC)

    report = protocol.build_row_data_report(row)

    assert len(report) == protocol.ROW_DATA_LENGTH
    assert report[:2] == b"\x00\x00"
    assert report[2] == 0x56
    assert report[23] == 0x34
    assert report[44] == 0x12
    assert report[22] == 0xCC
    assert report[43] == 0xBB
    assert report[64] == 0xAA


def test_device_set_color_enters_user_mode_then_writes_all_rows() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = Ite8291KeyboardDevice(features.append, outputs.append)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert features[0] == protocol.build_user_mode_report(25)
    assert features[1:] == [protocol.build_row_announce_report(row) for row in range(protocol.NUM_ROWS)]
    assert len(outputs) == protocol.NUM_ROWS
    assert outputs[0][2] == 0x56
    assert outputs[0][23] == 0x34
    assert outputs[0][44] == 0x12


def test_device_set_key_colors_can_skip_user_mode_reentry() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = Ite8291KeyboardDevice(features.append, outputs.append)

    device.set_key_colors({(0, 0): (1, 2, 3), (5, 20): (4, 5, 6)}, brightness=15, enable_user_mode=False)

    assert features == [protocol.build_row_announce_report(row) for row in range(protocol.NUM_ROWS)]
    assert len(outputs) == protocol.NUM_ROWS
    assert outputs[0][2] == 3
    assert outputs[0][23] == 2
    assert outputs[0][44] == 1
    assert outputs[5][22] == 6
    assert outputs[5][43] == 5
    assert outputs[5][64] == 4


def test_device_turn_off_sends_expected_report() -> None:
    features: list[bytes] = []
    device = Ite8291KeyboardDevice(features.append, lambda report: len(report))

    device.turn_off()

    assert features == [protocol.build_turn_off_report()]
    assert device.is_off() is True
    assert device.get_brightness() == 0


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8291Backend()

    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    assert backend.capabilities().per_key is True
    assert backend.capabilities().hardware_effects is False


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

    result = Ite8291Backend().probe()

    assert result.available is False
    assert "disabled" in (result.reason or "").lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr("src.core.backends.ite8291.backend._find_matching_supported_hidraw_device", lambda: None)

    result = Ite8291Backend().probe()

    assert result.available is False
    assert "no matching hidraw device" in result.reason.lower()


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x6008
        bcd_device = 0x0003
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8291)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr("src.core.backends.ite8291.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8291Backend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0x6008"


def test_backend_probe_rejects_zone_only_ce00_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xCE00
        bcd_device = 0x0002
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8291)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr("src.core.backends.ite8291.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8291Backend().probe()

    assert result.available is False
    assert "zone-only firmware variant" in result.reason.lower()
    assert result.identifiers["usb_bcd_device"] == "0x0002"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x600B
        bcd_device = 0x0003
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8291)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr("src.core.backends.ite8291.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8291Backend().probe()

    assert result.available is True
    assert result.confidence == 82
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8291.backend._find_matching_supported_hidraw_device", lambda: None)
    monkeypatch.setattr("src.core.backends.ite8291.hidraw.find_matching_hidraw_device", lambda **kwargs: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8291Backend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr("src.core.backends.ite8291.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8291Backend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr("src.core.backends.ite8291.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8291Backend().get_device()


def test_backend_get_device_propagates_unexpected_open_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8291.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected transport bug")),
    )

    with pytest.raises(AssertionError, match="unexpected transport bug"):
        Ite8291Backend().get_device()


def test_backend_get_device_returns_keyboard_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    features: list[bytes] = []
    outputs: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            features.append(bytes(report))
            return len(report)

        def write_output_report(self, report: bytes) -> int:
            outputs.append(bytes(report))
            return len(report)

    class DummyInfo:
        product_id = 0x6004
        bcd_device = 0x0003
        devnode = Path("/dev/hidraw7")

    monkeypatch.setattr(
        "src.core.backends.ite8291.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8291Backend().get_device()

    assert isinstance(device, Ite8291KeyboardDevice)
    device.set_key_colors({(0, 0): (0x12, 0x34, 0x56)}, brightness=25)
    assert features[0] == protocol.build_user_mode_report(25)
    assert outputs[0][2] == 0x56
    assert outputs[0][23] == 0x34
    assert outputs[0][44] == 0x12


def test_backend_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8291Backend()

    assert backend.dimensions() == (protocol.NUM_ROWS, protocol.NUM_COLS)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8291Backend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8291Backend().is_available() is True