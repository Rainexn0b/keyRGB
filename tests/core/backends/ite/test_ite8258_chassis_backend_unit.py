from __future__ import annotations

import pytest

from keyrgb.core.backends.ite8258_perkey_chassis import protocol
from keyrgb.core.backends.ite8258_perkey_chassis.device import Ite8258ChassisKeyboardDevice
from keyrgb.core.backends.ite8258_perkey_chassis.profile_coordinator import Ite8258ChassisProfileCoordinator


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
        0x01F5,
        0x01F6,
        0x01F7,
        0x01F8,
        0x01F9,
        0x01FA,
        0x01FB,
        0x01FC,
        0x01FD,
        0x01FE,
    )
    assert protocol.VENT_LED_IDS == (
        0x03E9,
        0x03EA,
        0x03EB,
        0x03EC,
        0x03ED,
        0x03EE,
        0x03EF,
        0x03F0,
        0x03F1,
        0x03F2,
        0x03F3,
        0x03F4,
        0x03F5,
        0x03F6,
        0x03F7,
        0x03F8,
        0x03F9,
        0x03FA,
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
    device = Ite8258ChassisKeyboardDevice(
        sent.append,
        profile_coordinator=Ite8258ChassisProfileCoordinator(),
    )

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    assert sent[2][:34].hex() == "07cbc0030101010106010b0202030004000502060001123456650100020003000400"
    assert sent[3][:5].hex() == "07cec00304"


def test_device_set_key_colors_maps_tuple_keys_to_keyboard_led_ids() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisKeyboardDevice(
        sent.append,
        profile_coordinator=Ite8258ChassisProfileCoordinator(),
    )

    device.set_key_colors({(0, 0): (255, 0, 0), (6, 15): (0, 255, 0)}, brightness=50)

    report = sent[2]
    assert report[0] == protocol.REPORT_ID
    assert report[1] == protocol.SAVE_PROFILE
    assert b"\x01\x00" in report
    assert b"\xa1\x00" in report
    assert sent[-1][:5].hex() == "07cec00309"


def test_device_set_key_colors_skips_sparse_and_generic_grid_gaps() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisKeyboardDevice(
        sent.append,
        profile_coordinator=Ite8258ChassisProfileCoordinator(),
    )

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
    assert b"\xaa\xbb\xcc" not in report
    assert b"\xdd\xee\xff" not in report
    assert sent[-1][:5].hex() == "07cec00309"


def test_protocol_builds_uniform_static_groups_for_leds() -> None:
    groups = protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (255, 0, 0))
    assert len(groups) == 1
    assert groups[0].mode == protocol.MODE_STATIC
    assert groups[0].colors == ((255, 0, 0),)
    assert groups[0].leds == protocol.LOGO_LED_IDS


def test_protocol_returns_empty_groups_for_empty_led_ids() -> None:
    assert protocol.build_uniform_static_groups_for_leds((), (255, 0, 0)) == ()


def test_device_coerce_helpers_and_error_edges() -> None:
    from keyrgb.core.backends.ite8258_perkey_chassis import device as device_mod

    assert device_mod._coerce_int("12") == 12
    with pytest.raises(ValueError, match="RGB"):
        device_mod._coerce_rgb(object())
    assert device_mod._coerce_rgb((300, -1, 10))  # clamped

    with pytest.raises(ValueError, match="tuple key"):
        device_mod._coerce_led_id((1, 2, 3))
    assert isinstance(device_mod._coerce_led_id((0, 0)), int)
    assert isinstance(device_mod._coerce_led_id(5), int)

    with pytest.raises(ValueError, match="tuple key"):
        device_mod._coerce_led_id_or_none((1,))
    assert device_mod._coerce_led_id_or_none((99, 99)) is None  # out of range -> None via ValueError

    assert device_mod._normalize_effect_name({"name": "Color Wave"}) == "color_wave"
    assert device_mod._normalize_effect_name(["Static"]) == "static"
    assert device_mod._normalize_effect_name("Rainbow") == "rainbow"
    assert device_mod._normalize_effect_name(None) == ""

    with pytest.raises(TypeError, match="callable"):
        Ite8258ChassisKeyboardDevice(None, profile_coordinator=Ite8258ChassisProfileCoordinator())  # type: ignore[arg-type]

    reports: list[bytes] = []

    def send(report: bytes) -> int:
        reports.append(report)
        return -1

    device = Ite8258ChassisKeyboardDevice(lambda r: 0, profile_coordinator=Ite8258ChassisProfileCoordinator())
    device._send_feature_report = send  # type: ignore[method-assign]
    with pytest.raises(OSError, match="feature report"):
        device._send(b"\x00")

    # black color / empty map / all black turns off
    device = Ite8258ChassisKeyboardDevice(lambda r: 0, profile_coordinator=Ite8258ChassisProfileCoordinator())
    device.set_color((0, 0, 0), brightness=50)
    assert device.is_off() is True
    device.set_color((1, 2, 3), brightness=0)
    assert device.is_off() is True
    device.set_key_colors({}, brightness=20)
    assert device.is_off() is True
    device.set_brightness(0)
    assert device.is_off() is True
    assert device.get_brightness() == 0

    # close swallows transport errors
    class _Bad:
        def close(self) -> None:
            raise OSError("gone")

    device = Ite8258ChassisKeyboardDevice(
        lambda r: 0,
        profile_coordinator=Ite8258ChassisProfileCoordinator(),
        transport=_Bad(),
    )
    device.close()
    assert device._transport is None
