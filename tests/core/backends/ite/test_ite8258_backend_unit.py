from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.base import BackendStability, ExperimentalEvidence
from src.core.backends.exceptions import BackendIOError
from src.core.backends.ite8258 import protocol
from src.core.backends.ite8258.backend import (
    Ite8258Backend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from src.core.backends.ite8258.device import Ite8258KeyboardDevice


def test_protocol_builds_turn_off_report() -> None:
    report = protocol.build_turn_off_report()

    assert len(report) == protocol.PACKET_SIZE
    assert report[:7].hex() == "07cb0300010101"
    assert report[7:] == bytes(protocol.PACKET_SIZE - 7)


def test_protocol_builds_brightness_report() -> None:
    report = protocol.build_set_brightness_report(5)

    assert len(report) == protocol.PACKET_SIZE
    assert report[:5].hex() == "07ce010005"
    assert report[5:] == bytes(protocol.PACKET_SIZE - 5)


def test_protocol_builds_uniform_static_group_report() -> None:
    report = protocol.build_save_profile_reports(1, protocol.build_uniform_static_groups((0x12, 0x34, 0x56)))[0]

    assert len(report) == protocol.PACKET_SIZE
    assert report[:26].hex() == "07cb46000101010106010b020203000400050206000112345618"
    assert report[26:34].hex() == "0100020003000400"


def test_protocol_groups_static_zone_colors_by_rgb_value() -> None:
    zone_colors = [(0, 0, 0) for _ in range(protocol.NUM_ZONES)]
    zone_colors[0] = (255, 0, 0)
    zone_colors[1] = (255, 0, 0)
    zone_colors[7] = (0, 255, 0)

    groups = protocol.build_static_groups(zone_colors)

    assert len(groups) == 3
    assert groups[0].colors == ((255, 0, 0),)
    assert groups[0].leds == (1, 2)
    assert groups[1].colors == ((0, 0, 0),)
    assert 3 in groups[1].leds
    assert 24 in groups[1].leds
    assert groups[2].colors == ((0, 255, 0),)
    assert groups[2].leds == (8,)


def test_protocol_builds_color_wave_effect_group_with_direction_and_color() -> None:
    groups = protocol.build_effect_groups("color_wave", speed=3, color=(0x10, 0x20, 0x30), direction="left")

    assert len(groups) == 1
    assert groups[0].mode == protocol.MODE_COLOR_WAVE
    assert groups[0].speed == 3
    assert groups[0].direction == protocol.DIRECTION_LEFT
    assert groups[0].color_mode == protocol.COLOR_MODE_CUSTOM
    assert groups[0].colors == ((0x10, 0x20, 0x30),)
    assert groups[0].leds == protocol.LED_IDS


def test_protocol_builds_rainbow_effect_group_with_spin_only() -> None:
    groups = protocol.build_effect_groups("rainbow", speed=2, direction="left")

    assert len(groups) == 1
    assert groups[0].mode == protocol.MODE_SCREW_RAINBOW
    assert groups[0].spin == protocol.SPIN_LEFT
    assert groups[0].direction == 0
    assert groups[0].color_mode == protocol.COLOR_MODE_NONE


def test_device_set_color_sends_group_report_then_brightness() -> None:
    sent: list[bytes] = []
    device = Ite8258KeyboardDevice(sent.append)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0][:26].hex() == "07cb46000101010106010b020203000400050206000112345618"
    assert sent[1][:5].hex() == "07ce010004"


def test_device_set_key_colors_maps_tuple_keys_to_24_zone_ids() -> None:
    sent: list[bytes] = []
    device = Ite8258KeyboardDevice(sent.append)

    device.set_key_colors({(0, 0): (255, 0, 0), (3, 5): (0, 255, 0)}, brightness=50)

    report = sent[0]
    assert report[0] == protocol.REPORT_ID
    assert report[1] == protocol.SAVE_PROFILE
    assert b"\x01\x00" in report
    assert b"\x18\x00" in report
    assert sent[-1][:5].hex() == "07ce010009"


def test_device_turn_off_sends_turn_off_report() -> None:
    sent: list[bytes] = []
    device = Ite8258KeyboardDevice(sent.append)

    device.turn_off()

    assert sent == [protocol.build_turn_off_report()]
    assert device.is_off() is True
    assert device.get_brightness() == 0


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8258Backend()

    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    caps = backend.capabilities()
    assert caps.per_key is True
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

    result = Ite8258Backend().probe()

    assert result.available is False
    assert "disabled" in result.reason.lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8258.backend._find_matching_supported_hidraw_device", lambda: None
    )

    result = Ite8258Backend().probe()

    assert result.available is False
    assert result.reason == "no matching hidraw device"


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC195
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr("src.core.backends.ite8258.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8258Backend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0xc195"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC195
        devnode = Path("/dev/hidraw7")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr("src.core.backends.ite8258.backend._find_matching_supported_hidraw_device", lambda: DummyMatch())

    result = Ite8258Backend().probe()

    assert result.available is True
    assert result.confidence == 83
    assert result.identifiers["hidraw"] == "/dev/hidraw7"


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.backends.ite8258.backend._find_matching_supported_hidraw_device", lambda: None)

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8258Backend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr("src.core.backends.ite8258.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8258Backend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr("src.core.backends.ite8258.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err))

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8258Backend().get_device()


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
        "src.core.backends.ite8258.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8258Backend().get_device()

    assert isinstance(device, Ite8258KeyboardDevice)
    device.set_effect({"name": "color_wave", "color": (0x12, 0x34, 0x56), "direction": "left", "brightness": 50})
    assert sent[0][1] == protocol.SAVE_PROFILE
    assert sent[1][:5].hex() == "07ce010009"


def test_backend_dimensions_effects_and_colors_are_fixed() -> None:
    backend = Ite8258Backend()

    assert backend.dimensions() == (protocol.NUM_ROWS, protocol.NUM_COLS)
    assert set(backend.effects()) == {
        "rainbow",
        "rainbow_wave",
        "color_change",
        "color_pulse",
        "color_wave",
        "smooth",
    }
    assert backend.colors() == {}


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8258Backend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8258Backend().is_available() is True