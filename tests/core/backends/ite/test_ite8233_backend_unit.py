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
        "src.core.backends.ite8233.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
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
        "src.core.backends.ite8233.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
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
        "src.core.backends.ite8233.backend._find_matching_supported_hidraw_device", lambda: DummyMatch()
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


def test_ite8233_get_device_propagates_unexpected_open_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = AssertionError("unexpected transport bug")
    monkeypatch.setattr(
        "src.core.backends.ite8233.backend._open_matching_transport", lambda: (_ for _ in ()).throw(err)
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
        "src.core.backends.ite8233.backend._open_matching_transport",
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


def test_ite8233_protocol_builds_expected_uniform_color_report() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56))

    assert report == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_uniform_color_report_for_7000() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56), product_id=0x7000)

    assert report == bytes((0x14, 0x01, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_uniform_color_report_for_6010() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56), product_id=0x6010)

    assert report == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_color_slot_report_for_7000() -> None:
    report = ite8233_protocol.build_color_slot_report(3, (0x12, 0x34, 0x56), product_id=0x7000)

    assert report == bytes((0x14, 0x01, 0x03, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_applies_vendor_color_scaling_quirk_for_6010(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    dmi_root = tmp_path / "dmi"
    dmi_root.mkdir()
    (dmi_root / "product_sku").write_text("STEPOL1XA04\n", encoding="utf-8")
    monkeypatch.setenv("KEYRGB_SYSFS_DMI_ROOT", str(dmi_root))

    report = ite8233_protocol.build_uniform_color_report((0xFF, 0xFF, 0xFF), product_id=0x6010)

    assert report == bytes((0x14, 0x00, 0x01, 0xFF, 0x64, 0x64, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_brightness_report() -> None:
    report = ite8233_protocol.build_brightness_report(37)

    assert report == bytes((0x08, 0x22, 0x01, 0x01, 37, 0x01, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_brightness_report_for_7000() -> None:
    report = ite8233_protocol.build_brightness_report(37, product_id=0x7000)

    assert report == bytes((0x08, 0x21, 0x01, 0x01, 37, 0x01, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_brightness_report_for_6010() -> None:
    report = ite8233_protocol.build_brightness_report(37, product_id=0x6010)

    assert report == bytes((0x08, 0x02, 0x01, 0x01, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_breathing_report_for_7000() -> None:
    report = ite8233_protocol.build_breathing_report(brightness=37, speed=4, product_id=0x7000)

    assert report == bytes((0x08, 0x21, 0x02, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_breathing_report_for_6010() -> None:
    report = ite8233_protocol.build_breathing_report(brightness=37, speed=4, product_id=0x6010)

    assert report == bytes((0x08, 0x02, 0x02, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_breathing_sequence_for_7000() -> None:
    reports = ite8233_protocol.build_breathing_reports((0x12, 0x34, 0x56), brightness=37, speed=4, product_id=0x7000)

    assert len(reports) == ite8233_protocol.COLOR_SLOT_COUNT + 1
    assert reports[0] == bytes((0x14, 0x01, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert reports[-1] == bytes((0x08, 0x21, 0x02, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_wave_report_for_7000() -> None:
    report = ite8233_protocol.build_wave_report(brightness=37, speed=4, product_id=0x7000)

    assert report == bytes((0x08, 0x21, 0x03, 0x04, 37, 0x01, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_bounce_report_for_7000() -> None:
    report = ite8233_protocol.build_bounce_report(brightness=37, speed=4, product_id=0x7000)

    assert report == bytes((0x08, 0x21, 0x04, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_off_sequence() -> None:
    reports = ite8233_protocol.build_turn_off_reports()

    assert reports == (
        bytes((0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x1A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    )


def test_ite8233_protocol_builds_expected_off_sequence_for_7000() -> None:
    reports = ite8233_protocol.build_turn_off_reports(product_id=0x7000)

    assert reports == (
        bytes((0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x1A, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    )


def test_ite8233_protocol_builds_expected_off_sequence_for_6010() -> None:
    reports = ite8233_protocol.build_turn_off_reports(product_id=0x6010)

    assert reports == (
        bytes((0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x08, 0x02, 0x01, 0x01, 0x00, 0x08, 0x00, 0x00)),
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


def test_ite8233_device_sends_7000_variant_reports() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_color((0x20, 0x40, 0x60), brightness=25)

    assert seen == [
        bytes((0x14, 0x01, 0x01, 0x10, 0x20, 0x30, 0x00, 0x00)),
        bytes((0x08, 0x21, 0x01, 0x01, 50, 0x01, 0x00, 0x00)),
    ]


def test_ite8233_device_sends_6010_variant_reports() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.set_color((0x20, 0x40, 0x60), brightness=25)

    assert seen == [
        bytes((0x14, 0x00, 0x01, 0x10, 0x20, 0x30, 0x00, 0x00)),
        bytes((0x08, 0x02, 0x01, 0x01, 50, 0x08, 0x00, 0x00)),
    ]


def test_ite8233_device_turn_off_sends_6010_variant_sequence() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.turn_off()

    assert seen == list(ite8233_protocol.build_turn_off_reports(product_id=0x6010))


def test_ite8233_device_supports_hidden_breathing_effect_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})

    assert device.keyrgb_hw_speed_policy == "inverted"
    assert seen[0] == bytes((0x14, 0x01, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert seen[6] == bytes((0x14, 0x01, 0x07, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert seen[-1] == bytes((0x08, 0x21, 0x02, 0x04, 50, 0x08, 0x00, 0x00))


def test_ite8233_device_supports_hidden_breathing_effect_for_6010() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})

    assert seen[0] == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert seen[6] == bytes((0x14, 0x00, 0x07, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert seen[-1] == bytes((0x08, 0x02, 0x02, 0x04, 50, 0x08, 0x00, 0x00))


def test_ite8233_device_rejects_hidden_breathing_effect_for_7001() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7001)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})


def test_ite8233_device_supports_hidden_wave_effect_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "wave", "brightness": 25, "speed": 7})

    assert seen == [bytes((0x08, 0x21, 0x03, 0x04, 50, 0x01, 0x00, 0x00))]


def test_ite8233_device_rejects_hidden_wave_effect_for_6010() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x6010)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "wave", "brightness": 25, "speed": 7})


def test_ite8233_device_rejects_hidden_wave_effect_for_7001() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7001)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "wave", "brightness": 25, "speed": 7})


def test_ite8233_device_supports_hidden_bounce_effect_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "bounce", "brightness": 25, "speed": 7})

    assert seen == [bytes((0x08, 0x21, 0x04, 0x04, 50, 0x08, 0x00, 0x00))]


def test_ite8233_device_supports_hidden_clash_alias_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "clash", "brightness": 25, "speed": 7})

    assert seen == [bytes((0x08, 0x21, 0x04, 0x04, 50, 0x08, 0x00, 0x00))]


def test_ite8233_device_rejects_hidden_bounce_effect_for_6010() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x6010)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "bounce", "brightness": 25, "speed": 7})


def test_ite8233_device_rejects_hidden_bounce_effect_for_7001() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7001)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "bounce", "brightness": 25, "speed": 7})


def test_ite8233_protocol_builds_expected_catchup_report_for_7000() -> None:
    report = ite8233_protocol.build_catchup_report(brightness=37, speed=4, product_id=0x7000)

    # mode 0x05 (MODE_MARQUEE), apply byte 0x01 (same as wave), 7000 variant 0x21
    assert report == bytes((0x08, 0x21, 0x05, 0x04, 37, 0x01, 0x00, 0x00))


def test_ite8233_device_supports_hidden_catchup_effect_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "catchup", "brightness": 25, "speed": 7})

    assert seen == [bytes((0x08, 0x21, 0x05, 0x04, 50, 0x01, 0x00, 0x00))]


def test_ite8233_device_supports_hidden_catch_up_alias_for_7000() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x7000)

    device.set_effect({"name": "catch_up", "brightness": 25, "speed": 7})

    assert seen == [bytes((0x08, 0x21, 0x05, 0x04, 50, 0x01, 0x00, 0x00))]


def test_ite8233_device_rejects_hidden_catchup_effect_for_6010() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x6010)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "catchup", "brightness": 25, "speed": 7})


def test_ite8233_device_rejects_hidden_catchup_effect_for_7001() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7001)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "catchup", "brightness": 25, "speed": 7})


def test_ite8233_protocol_builds_expected_flash_report_for_6010() -> None:
    report = ite8233_protocol.build_flash_report(brightness=37, speed=4, product_id=0x6010)

    # mode 0x11 (MODE_FLASH), apply byte 0x08, 6010 variant 0x02, direction 0x00 (none)
    assert report == bytes((0x08, 0x02, 0x11, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_flash_report_with_direction_for_6010() -> None:
    report = ite8233_protocol.build_flash_report(
        brightness=37, speed=4, direction=ite8233_protocol.FLASH_DIRECTION_RIGHT, product_id=0x6010
    )

    assert report == bytes((0x08, 0x02, 0x11, 0x04, 37, 0x08, 0x01, 0x00))


def test_ite8233_protocol_builds_expected_flash_sequence_for_6010() -> None:
    reports = ite8233_protocol.build_flash_reports(
        (0x12, 0x34, 0x56), brightness=37, speed=4, product_id=0x6010
    )

    assert len(reports) == ite8233_protocol.COLOR_SLOT_COUNT + 1
    assert reports[0] == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert reports[-1] == bytes((0x08, 0x02, 0x11, 0x04, 37, 0x08, 0x00, 0x00))


def test_ite8233_device_supports_hidden_flash_effect_for_6010() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.set_effect({"name": "flash", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7, "direction": "right"})

    assert len(seen) == ite8233_protocol.COLOR_SLOT_COUNT + 1
    assert seen[0] == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert seen[-1] == bytes((0x08, 0x02, 0x11, 0x04, 50, 0x08, 0x01, 0x00))


def test_ite8233_device_supports_hidden_flash_effect_no_direction_for_6010() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.set_effect({"name": "flash", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})

    assert seen[-1] == bytes((0x08, 0x02, 0x11, 0x04, 50, 0x08, 0x00, 0x00))


def test_ite8233_device_rejects_hidden_flash_effect_for_7000() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7000)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "flash", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})


def test_ite8233_device_rejects_hidden_flash_effect_for_7001() -> None:
    device = Ite8233LightbarDevice(lambda report: len(report), product_id=0x7001)

    with pytest.raises(RuntimeError, match="not supported"):
        device.set_effect({"name": "flash", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7})
