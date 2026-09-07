from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.backends.ite8258_perkey_chassis import (
    backend as _ite8258_chassis_backend_module,
    protocol,
)
from keyrgb.core.backends.ite8258_perkey_chassis.backend import Ite8258ChassisBackend
from keyrgb.core.backends.ite8258_perkey_chassis.device import (
    Ite8258ChassisKeyboardDevice,
    Ite8258ChassisZoneDevice,
)
from keyrgb.core.backends.ite8258_perkey_chassis.profile_coordinator import (
    Ite8258ChassisProfileCoordinator,
)


def _coordinator_with_primary_scene() -> Ite8258ChassisProfileCoordinator:
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(lambda _report: None, profile_coordinator=coordinator)
    keyboard.set_color((255, 255, 255), brightness=25)
    return coordinator


def test_zone_device_set_color_sends_complete_profile_without_global_brightness() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=_coordinator_with_primary_scene(),
    )

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    # The save-profile report should contain the logo LED ID 0x05DD (little-endian DD 05)
    assert b"\xdd\x05" in sent[2]
    assert len(sent) == 3


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
            profile_coordinator=_coordinator_with_primary_scene(),
        )
        device.set_color((255, 255, 255), brightness=25)

        # The encoded group should reference all expected LED IDs in order
        report = sent[2]
        offset = report.find(bytes([expected_leds[0] & 0xFF, (expected_leds[0] >> 8) & 0xFF]))
        assert offset > 0, f"zone {zone_name} missing first LED ID in report"
        for i, led_id in enumerate(expected_leds):
            assert report[offset + i * 2] == (led_id & 0xFF)
            assert report[offset + i * 2 + 1] == ((led_id >> 8) & 0xFF)


def test_zone_device_rejects_independent_positive_brightness() -> None:
    device = Ite8258ChassisZoneDevice(
        lambda _report: None,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=_coordinator_with_primary_scene(),
    )

    with pytest.raises(RuntimeError, match="primary keyboard"):
        device.set_brightness(25)


def test_backend_get_zone_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8258ChassisBackend().get_zone_device("logo")


def test_backend_get_zone_device_rejects_unknown_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    _ite8258_chassis_backend_module._transport_manager = None
    _ite8258_chassis_backend_module._profile_coordinators = {}
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
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    with pytest.raises(ValueError, match="Unknown ITE 8258 chassis zone"):
        Ite8258ChassisBackend().get_zone_device("unknown")


def test_backend_zone_first_stages_until_keyboard_profile_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    _ite8258_chassis_backend_module._transport_manager = None
    _ite8258_chassis_backend_module._profile_coordinators = {}
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
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    backend = Ite8258ChassisBackend()
    device = backend.get_zone_device("logo")

    assert isinstance(device, Ite8258ChassisZoneDevice)
    device.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    assert sent == []

    keyboard = backend.get_device()
    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)

    assert sent[0] == protocol.build_switch_profile_report()
    assert sent[1] == protocol.build_set_direct_mode_report(enabled=False)
    assert b"\xdd\x05" in sent[2]
    assert b"\xab\xcd\xef" in sent[2]


def test_backend_keyboard_and_zone_devices_share_one_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acquiring keyboard + zones opens hidraw once and shares the proxy."""
    _ite8258_chassis_backend_module._transport_manager = None
    _ite8258_chassis_backend_module._profile_coordinators = {}
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
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
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


def test_zone_device_turn_off_sends_complete_profile_with_black_zone() -> None:
    sent: list[bytes] = []
    device = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=_coordinator_with_primary_scene(),
    )

    device.turn_off()

    # Should send switch profile + direct off + the complete scene with a black logo group.
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


def test_composite_profile_zone_update_preserves_keyboard_and_sibling_groups() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )
    neon = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="neon",
        led_ids=protocol.NEON_LED_IDS,
        profile_coordinator=coordinator,
    )

    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    neon.set_color((0x10, 0x20, 0x30), brightness=25)
    sent.clear()

    logo.turn_off()

    expected_groups = (
        *protocol.build_uniform_static_groups((0x12, 0x34, 0x56)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0x10, 0x20, 0x30)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
    ]


def test_composite_profile_global_off_preserves_desired_children_until_explicit_edit() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )

    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    sent.clear()

    keyboard.turn_off()
    # Transient global-off cleanup must not write; desired logo colour is retained.
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        protocol.build_turn_off_report(),
    ]
    assert coordinator.output_suspended is True

    sent.clear()
    keyboard.set_color((0x01, 0x02, 0x03), brightness=25)

    restored_groups = (
        *protocol.build_uniform_static_groups((0x01, 0x02, 0x03)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAB, 0xCD, 0xEF)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, restored_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_composite_profile_child_edits_while_suspended_update_desired_scene() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )
    neon = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="neon",
        led_ids=protocol.NEON_LED_IDS,
        profile_coordinator=coordinator,
    )

    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    neon.set_color((0x10, 0x20, 0x30), brightness=25)
    sent.clear()

    keyboard.turn_off()
    after_off = len(sent)
    logo.turn_off()  # desired-off while suspended
    neon.set_color((0xAA, 0xBB, 0xCC), brightness=25)  # desired-on while suspended
    assert len(sent) == after_off

    sent.clear()
    keyboard.set_color((0x01, 0x02, 0x03), brightness=25)
    expected_groups = (
        *protocol.build_uniform_static_groups((0x01, 0x02, 0x03)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0xAA, 0xBB, 0xCC)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_zone_device_edges() -> None:
    coordinator = Ite8258ChassisProfileCoordinator()
    with pytest.raises(TypeError):
        Ite8258ChassisZoneDevice(None, zone_name="logo", led_ids=(1,), profile_coordinator=coordinator)  # type: ignore[arg-type]

    zone = Ite8258ChassisZoneDevice(
        lambda r: -1,
        zone_name="logo",
        led_ids=(0x05DD,),
        profile_coordinator=coordinator,
    )
    with pytest.raises(OSError, match="logo"):
        zone._send(b"\x00")

    empty = Ite8258ChassisZoneDevice(
        lambda r: 0,
        zone_name="logo",
        led_ids=(),
        profile_coordinator=coordinator,
        current_brightness=10,
    )
    empty.turn_off()
    assert empty.is_off() is True
    # empty led_ids path only flips logical off without rewriting brightness

    zone2 = Ite8258ChassisZoneDevice(
        lambda r: 0,
        zone_name="logo",
        led_ids=(0x05DD,),
        profile_coordinator=coordinator,
        current_brightness=10,
    )
    zone2.set_brightness(0)
    assert zone2.is_off() is True
