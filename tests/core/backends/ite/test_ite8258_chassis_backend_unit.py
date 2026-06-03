from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8258_chassis import protocol
from src.core.backends.ite8258_chassis.backend import (
    Ite8258ChassisBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8258_chassis.device import Ite8258ChassisKeyboardDevice


def test_protocol_builds_turn_off_report() -> None:
    report = protocol.build_turn_off_report()

    assert len(report) == protocol.PACKET_SIZE
    assert report[:7].hex() == "07cbc003010101"
    assert report[7:] == bytes(protocol.PACKET_SIZE - 7)


def test_protocol_builds_brightness_report() -> None:
    report = protocol.build_set_brightness_report(5)

    assert len(report) == protocol.PACKET_SIZE
    assert report[:5].hex() == "07cec00305"
    assert report[5:] == bytes(protocol.PACKET_SIZE - 5)


def test_protocol_builds_direct_mode_and_direct_color_reports() -> None:
    direct_on = protocol.build_set_direct_mode_report(enabled=True)
    direct_off = protocol.build_set_direct_mode_report(enabled=False)
    direct_colors = protocol.build_direct_color_report(((0x0001, (0x12, 0x34, 0x56)), (0x00A1, (0xAB, 0xCD, 0xEF))))

    assert direct_on[:6].hex() == "07d0c0030101"
    assert direct_off[:6].hex() == "07d0c0030201"
    assert direct_colors[:14].hex() == "07a1c0030100123456a100abcdef"


def test_direction_code_matches_83f5_implementation() -> None:
    # Left/right were swapped in the original translation; corrected per research.
    assert protocol._direction_code("left") == protocol.DIRECTION_LEFT == 0x04
    assert protocol._direction_code("right") == protocol.DIRECTION_RIGHT == 0x03
    assert protocol._direction_code("up") == protocol.DIRECTION_UP == 0x01
    assert protocol._direction_code("down") == protocol.DIRECTION_DOWN == 0x02
    assert protocol._direction_code("") == protocol.DIRECTION_RIGHT == 0x03


def test_led_id_from_row_col_matches_openrgb_legion7_gen10_matrix() -> None:
    assert protocol.led_id_from_row_col(0, 0) == 0x01
    assert protocol.led_id_from_row_col(0, 19) == 0x14
    assert protocol.led_id_from_row_col(1, 0) == 0x16
    assert protocol.led_id_from_row_col(6, 12) == 0x9C
    assert protocol.led_id_from_row_col(6, 15) == 0xA1

    with pytest.raises(ValueError, match="does not map"):
        protocol.led_id_from_row_col(1, 10)


def test_protocol_builds_uniform_static_group_report() -> None:
    report = protocol.build_save_profile_reports(1, protocol.build_uniform_static_groups((0x12, 0x34, 0x56)))[0]

    assert len(report) == protocol.PACKET_SIZE
    assert report[:34].hex() == "07cbc0030101010106010b0202030004000502060001123456650100020003000400"


def test_device_set_color_sends_profile_switch_direct_off_group_report_then_brightness() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisKeyboardDevice(sent.append)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    assert sent[2][:34].hex() == "07cbc0030101010106010b0202030004000502060001123456650100020003000400"
    assert sent[3][:5].hex() == "07cec00304"


def test_device_set_key_colors_maps_tuple_keys_to_keyboard_led_ids() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisKeyboardDevice(sent.append)

    device.set_key_colors({(0, 0): (255, 0, 0), (6, 15): (0, 255, 0)}, brightness=50)

    report = sent[2]
    assert report[0] == protocol.REPORT_ID
    assert report[1] == protocol.SAVE_PROFILE
    assert b"\x01\x00" in report
    assert b"\xA1\x00" in report
    assert sent[-1][:5].hex() == "07cec00309"


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8258ChassisBackend()

    assert backend.name == "ite8258-chassis"
    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    caps = backend.capabilities()
    assert caps.per_key is True
    assert caps.hardware_effects is True
    assert backend.dimensions() == (protocol.KEYBOARD_NUM_ROWS, protocol.KEYBOARD_NUM_COLS)
    assert set(backend.effects()) == {
        "rainbow",
        "rainbow_wave",
        "color_change",
        "color_pulse",
        "color_wave",
        "smooth",
        "rain",
        "ripple",
        "audio_bounce",
        "audio_ripple",
        "type",
    }
    assert backend.colors() == {}


def test_find_matching_supported_hidraw_device_uses_forced_existing_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forced = tmp_path / "hidraw11"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv(protocol.HIDRAW_PATH_ENV, str(forced))

    info = _find_matching_supported_hidraw_device()

    assert info is not None
    assert info.devnode == forced
    assert info.vendor_id == protocol.VENDOR_ID
    assert info.product_id == protocol.SUPPORTED_PRODUCT_IDS[0]


def test_backend_probe_reports_unavailable_when_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert "disabled" in result.reason.lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._find_matching_supported_hidraw_device", lambda: None
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert result.reason == "no matching hidraw device"


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC197
        devnode = Path("/dev/hidraw11")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0xc197"
    assert result.identifiers["hidraw"] == "/dev/hidraw11"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC197
        devnode = Path("/dev/hidraw11")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is True
    assert result.confidence == 83
    assert result.identifiers["hidraw"] == "/dev/hidraw11"


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8258_chassis.backend._find_matching_supported_hidraw_device", lambda: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_returns_keyboard_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = Path("/dev/hidraw11")

    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8258ChassisBackend().get_device()

    assert isinstance(device, Ite8258ChassisKeyboardDevice)
    device.set_effect({"name": "color_wave", "color": (0x12, 0x34, 0x56), "direction": "left", "brightness": 50})
    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    assert sent[2][1] == protocol.SAVE_PROFILE
    assert sent[3][:5].hex() == "07cec00309"


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8258ChassisBackend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8258ChassisBackend().is_available() is True