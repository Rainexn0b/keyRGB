from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang import (
    protocol as tongfang_protocol,
)


def test_tongfang_lightbar_protocol_constants_match_openrgb_evidence() -> None:
    assert tongfang_protocol.VENDOR_ID == 0x048D
    assert tongfang_protocol.PRODUCT_ID == 0x6005
    assert tongfang_protocol.SUPPORTED_PRODUCT_IDS == (0x6005,)
    assert tongfang_protocol.DEFAULT_PRODUCT_ID == 0x6005
    assert tongfang_protocol.HIDRAW_PATH_ENV == "KEYRGB_ITE8291_TONGFANG_LIGHTBAR_HIDRAW_PATH"
    assert tongfang_protocol.USAGE_PAGE == 0xFF03
    assert tongfang_protocol.USAGE == 0x01
    assert tongfang_protocol.FEATURE_REPORT_LENGTH == 9
    assert tongfang_protocol.OUTPUT_REPORT_LENGTH == 65
    assert tongfang_protocol.DECLARED_LED_COUNT == 22
    assert tongfang_protocol.ADDRESSABLE_TRIPLET_COUNT == 21
    assert (tongfang_protocol.BRIGHTNESS_MIN, tongfang_protocol.BRIGHTNESS_MAX) == (0, 50)
    assert (tongfang_protocol.SPEED_MIN, tongfang_protocol.SPEED_MAX) == (0, 10)


def test_tongfang_lightbar_protocol_does_not_reuse_ite8233_tables() -> None:
    source = Path(tongfang_protocol.__file__).read_text(encoding="utf-8")

    assert "ite8233" not in source.lower()
    assert "6010" not in source
    assert "0x7000" not in source and "0x7001" not in source


def test_tongfang_lightbar_protocol_builds_expected_off_report() -> None:
    report = tongfang_protocol.build_off_report()

    assert report == bytes((0x00, 0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
    assert len(report) == tongfang_protocol.FEATURE_REPORT_LENGTH


def test_tongfang_lightbar_protocol_builds_expected_direct_mode_report() -> None:
    report = tongfang_protocol.build_direct_mode_report(brightness=25, speed=5)

    assert report == bytes((0x00, 0x08, 0x02, 0x33, 0x05, 0x19, 0x08, 0x00, 0x00))


def test_tongfang_lightbar_protocol_builds_expected_effect_mode_reports() -> None:
    assert tongfang_protocol.build_mode_report(mode=0x02, brightness=25, speed=5) == bytes(
        (0x00, 0x08, 0x02, 0x02, 0x05, 0x19, 0x08, 0x00, 0x00)
    )
    assert tongfang_protocol.build_mode_report(mode=0x20, brightness=50, speed=10) == bytes(
        (0x00, 0x08, 0x02, 0x20, 0x0A, 0x32, 0x08, 0x00, 0x00)
    )
    assert tongfang_protocol.build_mode_report(mode=0x0A, brightness=0, speed=0) == bytes(
        (0x00, 0x08, 0x02, 0x0A, 0x00, 0x00, 0x08, 0x00, 0x00)
    )


def test_tongfang_lightbar_protocol_clamps_mode_brightness_and_speed() -> None:
    report = tongfang_protocol.build_mode_report(mode=0x02, brightness=999, speed=999)

    assert report == bytes((0x00, 0x08, 0x02, 0x02, 0x0A, 0x32, 0x08, 0x00, 0x00))

    report = tongfang_protocol.build_mode_report(mode=0x02, brightness=-7, speed=-7)

    assert report == bytes((0x00, 0x08, 0x02, 0x02, 0x00, 0x00, 0x08, 0x00, 0x00))


def test_tongfang_lightbar_protocol_builds_expected_begin_and_commit_reports() -> None:
    assert tongfang_protocol.build_begin_report() == bytes((0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
    assert tongfang_protocol.build_commit_report() == bytes((0x00, 0x12, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00))


def test_tongfang_lightbar_protocol_builds_expected_effect_color_report() -> None:
    report = tongfang_protocol.build_effect_color_report(3, (0x12, 0x34, 0x56))

    assert report == bytes((0x00, 0x14, 0x00, 0x03, 0x12, 0x34, 0x56, 0x00, 0x00))


def test_tongfang_lightbar_protocol_builds_seven_repeated_effect_color_slots() -> None:
    reports = tongfang_protocol.build_effect_color_reports((0x12, 0x34, 0x56))

    assert len(reports) == tongfang_protocol.EFFECT_COLOR_SLOT_COUNT == 7
    assert [bytes(report)[3] for report in reports] == [1, 2, 3, 4, 5, 6, 7]
    assert all(
        bytes(report)[:3] == bytes((0x00, 0x14, 0x00)) and bytes(report)[4:7] == bytes((0x12, 0x34, 0x56))
        for report in reports
    )


def test_tongfang_lightbar_protocol_direct_frame_bounds_and_rbg_order() -> None:
    frame = tongfang_protocol.build_direct_frame((0x12, 0x34, 0x56))

    assert len(frame) == 65
    assert frame[0] == 0x00
    # R,B,G ordering per triplet.
    assert frame[1:4] == bytes((0x12, 0x56, 0x34))
    assert frame[61:64] == bytes((0x12, 0x56, 0x34))
    # Only complete triplets in bytes 1..63; trailing byte stays zero.
    assert frame[64] == 0x00
    assert frame[1:64] == bytes((0x12, 0x56, 0x34)) * 21


def test_tongfang_lightbar_protocol_direct_frame_clamps_channels() -> None:
    frame = tongfang_protocol.build_direct_frame((300, -10, 128))

    assert frame[1:4] == bytes((0xFF, 0x80, 0x00))
    assert len(frame) == 65


def test_tongfang_lightbar_protocol_rejects_unknown_product_id() -> None:
    with pytest.raises(ValueError, match="0xce00"):
        tongfang_protocol.normalize_product_id(0xCE00)

    assert tongfang_protocol.normalize_product_id(None) == 0x6005
    assert tongfang_protocol.normalize_product_id(0x6005) == 0x6005


def test_tongfang_lightbar_protocol_exposes_no_save_builder() -> None:
    assert not hasattr(tongfang_protocol, "build_save_report")
