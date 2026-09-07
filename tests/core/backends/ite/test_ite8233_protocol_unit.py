from __future__ import annotations

import pytest

from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo import (
    protocol as ite8233_protocol,
)
from keyrgb.core.effects import colors


def test_ite8233_protocol_builds_expected_uniform_color_report() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56))

    assert report == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_scale_color_for_brightness_is_shared_helper() -> None:
    # The backend re-exports the backend-neutral shared helper (no duplicate logic).
    assert ite8233_protocol.scale_color_for_brightness is colors.scale_color_for_brightness

    samples = [
        ((0x20, 0x40, 0x60), 0),
        ((0x20, 0x40, 0x60), 25),
        ((0x20, 0x40, 0x60), 50),
        ((300, -10, 128), 25),
        ((10.7, 20.3, 30.9), 50),
    ]
    for color, brightness in samples:
        assert ite8233_protocol.scale_color_for_brightness(color, brightness) == colors.scale_color_for_brightness(
            color, brightness
        )


def test_ite8233_protocol_builds_expected_uniform_color_report_for_7000() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56), product_id=0x7000)

    assert report == bytes((0x14, 0x01, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_uniform_color_report_for_6010() -> None:
    report = ite8233_protocol.build_uniform_color_report((0x12, 0x34, 0x56), product_id=0x6010)

    assert report == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_builds_expected_color_slot_report_for_7000() -> None:
    report = ite8233_protocol.build_color_slot_report(3, (0x12, 0x34, 0x56), product_id=0x7000)

    assert report == bytes((0x14, 0x01, 0x03, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_ite8233_protocol_applies_vendor_color_scaling_quirk_for_6010(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
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


def test_ite8233_protocol_builds_expected_catchup_report_for_7000() -> None:
    report = ite8233_protocol.build_catchup_report(brightness=37, speed=4, product_id=0x7000)

    # mode 0x05 (MODE_MARQUEE), apply byte 0x01 (same as wave), 7000 variant 0x21
    assert report == bytes((0x08, 0x21, 0x05, 0x04, 37, 0x01, 0x00, 0x00))


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
    reports = ite8233_protocol.build_flash_reports((0x12, 0x34, 0x56), brightness=37, speed=4, product_id=0x6010)

    assert len(reports) == ite8233_protocol.COLOR_SLOT_COUNT + 1
    assert reports[0] == bytes((0x14, 0x00, 0x01, 0x12, 0x34, 0x56, 0x00, 0x00))
    assert reports[-1] == bytes((0x08, 0x02, 0x11, 0x04, 37, 0x08, 0x00, 0x00))
