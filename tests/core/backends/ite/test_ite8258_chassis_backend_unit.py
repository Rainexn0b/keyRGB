from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8258_chassis import backend as _ite8258_chassis_backend_module
from src.core.backends.ite8258_chassis import protocol
from src.core.backends.ite8258_chassis.backend import (
    Ite8258ChassisBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8258_chassis.device import (
    Ite8258ChassisKeyboardDevice,
    Ite8258ChassisZoneDevice,
)


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


def test_chassis_zone_led_ids_use_16_bit_codes_from_83f5_implementation() -> None:
    # Low-byte constants were truncated; corrected to full 16-bit codes per research.
    assert protocol.LOGO_LED_IDS == (0x05DD,)
    assert protocol.NEON_LED_IDS == (
        0x01F5, 0x01F6, 0x01F7, 0x01F8, 0x01F9, 0x01FA,
        0x01FB, 0x01FC, 0x01FD, 0x01FE,
    )
    assert protocol.VENT_LED_IDS == (
        0x03E9, 0x03EA, 0x03EB, 0x03EC, 0x03ED, 0x03EE, 0x03EF,
        0x03F0, 0x03F1, 0x03F2, 0x03F3, 0x03F4, 0x03F5, 0x03F6,
        0x03F7, 0x03F8, 0x03F9, 0x03FA,
    )


def test_build_direct_color_emits_correct_16_bit_led_ids_for_chassis_zones() -> None:
    # Logo 0x05DD → little-endian bytes DD 05
    logo_report = protocol.build_direct_color_report(((0x05DD, (255, 0, 0)),))
    assert logo_report[4:6].hex() == "dd05"
    assert logo_report[6:9].hex() == "ff0000"

    # Neon 0x01F5 → little-endian bytes F5 01
    neon_report = protocol.build_direct_color_report(((0x01F5, (0, 255, 0)),))
    assert neon_report[4:6].hex() == "f501"
    assert neon_report[6:9].hex() == "00ff00"

    # Vent 0x03E9 → little-endian bytes E9 03
    vent_report = protocol.build_direct_color_report(((0x03E9, (0, 0, 255)),))
    assert vent_report[4:6].hex() == "e903"
    assert vent_report[6:9].hex() == "0000ff"


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


def test_device_set_key_colors_skips_sparse_and_generic_grid_gaps() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisKeyboardDevice(sent.append)

    device.set_key_colors(
        {
            (0, 0): (0x12, 0x34, 0x56),
            (1, 10): (0xAA, 0xBB, 0xCC),
            (0, 20): (0xDD, 0xEE, 0xFF),
        },
        brightness=50,
    )

    report = sent[2]
    assert b"\x01\x00" in report
    assert b"\x12\x34\x56" in report
    assert b"\xAA\xBB\xCC" not in report
    assert b"\xDD\xEE\xFF" not in report
    assert sent[-1][:5].hex() == "07cec00309"


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8258ChassisBackend()

    assert backend.name == "ite8258_chassis"
    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    caps = backend.capabilities()
    assert caps.per_key is True
    assert caps.hardware_effects is True
    assert backend.dimensions() == (protocol.KEYBOARD_NUM_ROWS, protocol.KEYBOARD_NUM_COLS)
    assert backend.diagnostics()["keyboard_matrix"] == {
        "rows": 7,
        "cols": 20,
        "matrix_cells": 140,
        "mapped_leds": 101,
        "keyboard_led_ids": 101,
        "sparse": True,
        "sparse_holes": 39,
        "row_mapped_counts": [20, 18, 17, 17, 15, 11, 3],
    }
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

def test_protocol_builds_uniform_static_groups_for_leds() -> None:
    groups = protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (255, 0, 0))
    assert len(groups) == 1
    assert groups[0].mode == protocol.MODE_STATIC
    assert groups[0].colors == ((255, 0, 0),)
    assert groups[0].leds == protocol.LOGO_LED_IDS


def test_protocol_returns_empty_groups_for_empty_led_ids() -> None:
    assert protocol.build_uniform_static_groups_for_leds((), (255, 0, 0)) == ()


def test_zone_device_set_color_sends_profile_switch_direct_off_group_report_then_brightness() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
    )

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    # The save-profile report should contain the logo LED ID 0x05DD (little-endian DD 05)
    assert b"\xdd\x05" in sent[2]
    assert sent[3][:5].hex() == "07cec00304"


def test_zone_device_uses_correct_led_ids_for_each_zone() -> None:
    zones = [
        ("logo", protocol.LOGO_LED_IDS),
        ("neon", protocol.NEON_LED_IDS),
        ("vent", protocol.VENT_LED_IDS),
    ]

    for zone_name, expected_leds in zones:
        sent: list[bytes] = []
        device = Ite8258ChassisZoneDevice(
            sent.append,
            zone_name=zone_name,
            led_ids=expected_leds,
        )
        device.set_color((255, 255, 255), brightness=25)

        # The encoded group should reference all expected LED IDs in order
        report = sent[2]
        offset = report.find(bytes([expected_leds[0] & 0xFF, (expected_leds[0] >> 8) & 0xFF]))
        assert offset > 0, f"zone {zone_name} missing first LED ID in report"
        for i, led_id in enumerate(expected_leds):
            assert report[offset + i * 2] == (led_id & 0xFF)
            assert report[offset + i * 2 + 1] == ((led_id >> 8) & 0xFF)


def test_backend_get_zone_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8258ChassisBackend().get_zone_device("logo")


def test_backend_get_zone_device_rejects_unknown_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    _ite8258_chassis_backend_module._transport_manager = None
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

        def close(self) -> None:
            pass

    class DummyInfo:
        devnode = Path("/dev/hidraw11")

    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    with pytest.raises(ValueError, match="Unknown ITE 8258 chassis zone"):
        Ite8258ChassisBackend().get_zone_device("unknown")


def test_backend_get_zone_device_returns_zone_device_for_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    _ite8258_chassis_backend_module._transport_manager = None
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

        def close(self) -> None:
            pass

    class DummyInfo:
        devnode = Path("/dev/hidraw11")

    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8258ChassisBackend().get_zone_device("logo")

    assert isinstance(device, Ite8258ChassisZoneDevice)
    device.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    assert b"\xdd\x05" in sent[2]


def test_backend_keyboard_and_zone_devices_share_one_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acquiring keyboard + zones opens hidraw once and shares the proxy."""
    _ite8258_chassis_backend_module._transport_manager = None
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    open_count = [0]

    class DummyTransport:
        def __init__(self) -> None:
            self.closed = False

        def send_feature_report(self, report: bytes) -> int:
            return len(report)

        def close(self) -> None:
            self.closed = True

    class DummyInfo:
        devnode = Path("/dev/hidraw11")

    def _opener() -> tuple[DummyTransport, DummyInfo]:
        open_count[0] += 1
        return DummyTransport(), DummyInfo()

    monkeypatch.setattr(
        "src.core.backends.ite8258_chassis.backend._open_matching_transport",
        _opener,
    )

    backend = Ite8258ChassisBackend()
    keyboard = backend.get_device()
    logo = backend.get_zone_device("logo")
    neon = backend.get_zone_device("neon")

    assert open_count[0] == 1

    logo.close()
    assert open_count[0] == 1

    neon.close()
    assert open_count[0] == 1

    keyboard.close()
    assert open_count[0] == 1  # opener still only called once


def test_zone_device_turn_off_sends_zone_scoped_black_static_groups() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
    )

    device.turn_off()

    # Should send switch profile + direct off + save-profile with black group
    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    # The save-profile report should contain the logo LED ID 0x05DD, not the global turn-off bytes 01 01
    report = sent[2]
    assert b"\xdd\x05" in report
    # Group header: 01 06 01 0b 02 02 03 00 04 00 05 02 06 00
    # Then color count 01, color bytes, LED count 01, LED id dd 05
    # Color starts at offset 22 after the 14-byte header + 1 color-count byte + 6 padding/header bytes
    # Easier: search for the black color sequence just before the LED id
    dd_offset = report.find(b"\xdd\x05")
    assert dd_offset > 4
    assert report[dd_offset - 4 : dd_offset - 1].hex() == "000000"  # black color immediately before LED id
    # Should NOT send a global brightness command after turn_off
    assert len(sent) == 3
