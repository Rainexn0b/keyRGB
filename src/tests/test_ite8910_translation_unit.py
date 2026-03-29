from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.backends.ite8910 import Ite8910Backend, Ite8910KeyboardDevice
from src.core.backends.base import BackendStability
from src.core.backends.ite8910.protocol import (
    Ite8910Effect,
    Ite8910ProtocolState,
    KNOWN_LED_IDS,
    build_brightness_speed_report_raw,
    build_effect_reports,
    build_effect_report,
    build_led_color_report,
    build_reset_report,
    led_id_from_row_col,
    raw_brightness_from_ui,
    raw_speed_from_effect_speed,
)


def test_brightness_speed_report_matches_upstream_reference() -> None:
    assert build_brightness_speed_report_raw(0x00, 0x00).hex() == "cc0900000000"
    assert build_brightness_speed_report_raw(0x0A, 0x02).hex() == "cc090a020000"
    assert build_brightness_speed_report_raw(0x0C, 0x09).hex() == "cc090a090000"


@pytest.mark.parametrize(
    ("effect", "expected_hex"),
    [
        (Ite8910Effect.RAINBOW_WAVE, "cc0004000000"),
        (Ite8910Effect.BREATHING, "cc0a00000000"),
        (Ite8910Effect.SCAN, "cc000a000000"),
        (Ite8910Effect.FLASHING, "cc0b00000000"),
        (Ite8910Effect.RANDOM, "cc0009000000"),
        (Ite8910Effect.SNAKE, "cc000b000000"),
        (Ite8910Effect.SPECTRUM_CYCLE, "cc0002000000"),
    ],
)
def test_effect_reports_match_upstream_reference(
    effect: Ite8910Effect,
    expected_hex: str,
) -> None:
    assert build_effect_report(effect).hex() == expected_hex


def test_reset_report_matches_upstream_reference() -> None:
    assert build_reset_report().hex() == "cc000c000000"


def test_led_color_report_matches_upstream_reference_shape() -> None:
    assert build_led_color_report(0x6E, (0x11, 0x22, 0x33)).hex() == "cc016e112233"


def test_led_id_from_row_col_matches_vendor_formula() -> None:
    assert led_id_from_row_col(0, 0) == 0x00
    assert led_id_from_row_col(1, 0) == 0x20
    assert led_id_from_row_col(2, 10) == 0x4A
    assert led_id_from_row_col(5, 19) == 0xB3


def test_known_led_ids_match_full_reverse_engineered_matrix() -> None:
    assert len(KNOWN_LED_IDS) == 120
    assert KNOWN_LED_IDS[:6] == (0, 1, 2, 3, 4, 5)
    assert 20 not in KNOWN_LED_IDS
    assert 31 not in KNOWN_LED_IDS
    assert 32 in KNOWN_LED_IDS
    assert 44 in KNOWN_LED_IDS
    assert 51 in KNOWN_LED_IDS
    assert 109 in KNOWN_LED_IDS
    assert 115 in KNOWN_LED_IDS
    assert 129 in KNOWN_LED_IDS
    assert 147 in KNOWN_LED_IDS
    assert 168 in KNOWN_LED_IDS
    assert KNOWN_LED_IDS[-1] == 179


def test_protocol_state_preserves_brightness_and_speed_like_upstream_c() -> None:
    state = Ite8910ProtocolState()

    assert state.set_brightness_raw(0x0A).hex() == "cc090a000000"
    assert state.current_brightness_raw == 0x0A
    assert state.current_speed_raw == 0x00

    assert state.set_speed_raw(0x02).hex() == "cc090a020000"
    assert state.current_brightness_raw == 0x0A
    assert state.current_speed_raw == 0x02


def test_reset_does_not_mutate_protocol_state() -> None:
    state = Ite8910ProtocolState(current_brightness_raw=0x07, current_speed_raw=0x02)

    assert state.reset() == build_reset_report()
    assert state.current_brightness_raw == 0x07
    assert state.current_speed_raw == 0x02


def test_raw_brightness_from_ui_preserves_nonzero_values() -> None:
    assert raw_brightness_from_ui(0) == 0
    assert raw_brightness_from_ui(1) == 1
    assert raw_brightness_from_ui(25) == 5
    assert raw_brightness_from_ui(50) == 10


def test_raw_speed_from_effect_speed_clamps_to_firmware_range() -> None:
    assert raw_speed_from_effect_speed(0) == 0
    assert raw_speed_from_effect_speed(5) == 5
    assert raw_speed_from_effect_speed(10) == 10
    assert raw_speed_from_effect_speed(15) == 10


def test_device_translates_row_col_writes_to_led_reports() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_key_colors(
        {
            (2, 10): (255, 0, 0),
            (0, 0): (1, 2, 3),
        },
        brightness=25,
        enable_user_mode=True,
    )

    assert sent[0] == build_reset_report()
    for i, led_id in enumerate(KNOWN_LED_IDS):
        assert sent[1 + i] == build_led_color_report(led_id, (0, 0, 0))
    brightness_idx = 1 + len(KNOWN_LED_IDS)
    assert sent[brightness_idx] == build_brightness_speed_report_raw(0x05, 0x00)
    assert sent[brightness_idx + 1] == build_led_color_report(0x4A, (255, 0, 0))
    assert sent[brightness_idx + 2] == build_led_color_report(0x00, (1, 2, 3))


def test_device_set_color_uses_known_led_ids_from_upstream_comment() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_color((0x12, 0x34, 0x56), brightness=10)

    assert sent[0] == build_reset_report()
    brightness_idx = 1 + len(KNOWN_LED_IDS)
    assert sent[brightness_idx] == build_brightness_speed_report_raw(0x02, 0x00)
    led_reports = sent[brightness_idx + 1 :]
    assert len(led_reports) == len(KNOWN_LED_IDS)
    assert led_reports[0] == build_led_color_report(KNOWN_LED_IDS[0], (0x12, 0x34, 0x56))
    assert led_reports[-1] == build_led_color_report(KNOWN_LED_IDS[-1], (0x12, 0x34, 0x56))


def test_device_effect_payload_applies_brightness_speed_then_effect_sequence() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_effect(
        {
            "name": "wave",
            "brightness": 25,
            "speed": 10,
            "direction": "right",
            "color": (0x12, 0x34, 0x56),
        }
    )

    assert sent[0] == build_brightness_speed_report_raw(0x05, 0x0A)
    assert sent[1:] == build_effect_reports(Ite8910Effect.RAINBOW_WAVE, [(0x12, 0x34, 0x56)], "right")


def test_device_effect_payload_uses_preset_direction_when_no_color_supplied() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_effect({"name": "snake", "brightness": 20, "speed": 4, "direction": "down_right"})

    assert sent[0] == build_brightness_speed_report_raw(0x04, 0x04)
    assert sent[1:] == build_effect_reports(Ite8910Effect.SNAKE, None, "down_right")


def test_device_set_key_colors_without_user_mode_still_clears_before_write() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_key_colors({(0, 0): (1, 2, 3)}, brightness=25, enable_user_mode=False)

    assert sent[0] == build_reset_report()
    brightness_idx = 1 + len(KNOWN_LED_IDS)
    assert sent[brightness_idx] == build_brightness_speed_report_raw(0x05, 0x00)
    assert sent[brightness_idx + 1] == build_led_color_report(0x00, (1, 2, 3))


def test_backend_effect_builders_return_dict_payloads() -> None:
    from src.core.backends.base import HardwareEffectDescriptor

    backend = Ite8910Backend()
    effects = backend.effects()
    wave_builder = effects["wave"]

    assert isinstance(wave_builder, HardwareEffectDescriptor)

    payload = wave_builder(speed=4, brightness=25)
    assert payload == {"name": "rainbow_wave", "speed": 4, "brightness": 25}

    payload_with_dir = wave_builder(speed=4, brightness=25, direction="up_left")
    assert payload_with_dir["direction"] == "up_left"

    payload_with_color = wave_builder(speed=4, brightness=25, color=(255, 0, 0))
    assert payload_with_color["color"] == (255, 0, 0)

    assert "rainbow" in effects
    assert "snake" in effects
    assert backend.stability == BackendStability.VALIDATED

    snake_payload = effects["snake"](speed=3, brightness=20, direction="down_right")
    assert snake_payload["direction"] == "down_right"

    with pytest.raises(ValueError, match="not needed"):
        effects["spectrum_cycle"](speed=4, brightness=25, direction="up")


def test_backend_get_device_returns_keyboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTransport:
        def __init__(self):
            self.sent: list[bytes] = []

        def send_feature_report(self, report: bytes) -> int:
            self.sent.append(bytes(report))
            return len(report)

    transport = FakeTransport()
    monkeypatch.setattr(
        "src.core.backends.ite8910.backend.open_matching_hidraw_transport",
        lambda *_a, **_k: (transport, SimpleNamespace(devnode="/dev/hidraw7")),
    )

    backend = Ite8910Backend()
    kb = backend.get_device()
    assert isinstance(kb, Ite8910KeyboardDevice)
    kb.set_brightness(25)
    assert transport.sent[0] == build_brightness_speed_report_raw(0x05, 0x00)


def test_backend_probe_reports_available_when_device_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr(
        "src.core.backends.ite8910.backend.find_matching_hidraw_device",
        lambda *_a, **_k: SimpleNamespace(
            vendor_id=0x048D,
            product_id=0x8910,
            devnode="/dev/hidraw7",
            hid_name="ITE Device(829x)",
        ),
    )

    backend = Ite8910Backend()
    res = backend.probe()
    assert res.available is True
    assert res.identifiers["hidraw"] == "/dev/hidraw7"
    assert "hidraw device present" in (res.reason or "")
