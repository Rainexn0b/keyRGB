from __future__ import annotations

import pytest

from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo import (
    protocol as ite8233_protocol,
)
from keyrgb.core.backends.ite8233_none_chassis_lightbar_clevo.device import Ite8233LightbarDevice


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


def test_ite8233_device_supports_hidden_flash_effect_for_6010() -> None:
    seen: list[bytes] = []
    device = Ite8233LightbarDevice(lambda report: seen.append(bytes(report)) or len(report), product_id=0x6010)

    device.set_effect(
        {"name": "flash", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 7, "direction": "right"}
    )

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
