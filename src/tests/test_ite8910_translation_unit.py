from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.backends.ite8910 import Ite8910Backend, Ite8910KeyboardDevice
from src.core.backends.base import ExperimentalEvidence
from src.core.backends.ite8910.protocol import (
    Ite8910Effect,
    Ite8910ProtocolState,
    KNOWN_LED_IDS,
    build_brightness_speed_report_raw,
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
    assert build_brightness_speed_report_raw(0x0C, 0x09).hex() == "cc090a020000"


@pytest.mark.parametrize(
    ("effect", "expected_hex"),
    [
        (Ite8910Effect.WAVE, "cc0004000000"),
        (Ite8910Effect.BREATHING, "cc0a00000000"),
        (Ite8910Effect.SCAN, "cc000a000000"),
        (Ite8910Effect.FLASHING, "cc0b00000000"),
        (Ite8910Effect.RANDOM, "cc0009000000"),
        (Ite8910Effect.RIPPLE, "cc0700000000"),
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


def test_raw_speed_from_effect_speed_maps_keyrgb_range_to_three_steps() -> None:
    assert raw_speed_from_effect_speed(1) == 0
    assert raw_speed_from_effect_speed(5) == 1
    assert raw_speed_from_effect_speed(10) == 2


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
    assert sent[1] == build_brightness_speed_report_raw(0x05, 0x00)
    assert sent[2] == build_led_color_report(0x4A, (255, 0, 0))
    assert sent[3] == build_led_color_report(0x00, (1, 2, 3))


def test_device_set_color_uses_known_led_ids_from_upstream_comment() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_color((0x12, 0x34, 0x56), brightness=10)

    assert sent[0] == build_reset_report()
    assert sent[1] == build_brightness_speed_report_raw(0x02, 0x00)
    led_reports = sent[2:]
    assert len(led_reports) == len(KNOWN_LED_IDS)
    assert led_reports[0] == build_led_color_report(KNOWN_LED_IDS[0], (0x12, 0x34, 0x56))
    assert led_reports[-1] == build_led_color_report(KNOWN_LED_IDS[-1], (0x12, 0x34, 0x56))


def test_device_effect_payload_applies_brightness_speed_then_effect() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_effect({"name": "wave", "brightness": 25, "speed": 10})

    assert sent[0] == build_brightness_speed_report_raw(0x05, 0x02)
    assert sent[1] == build_effect_report("wave")


def test_device_set_key_colors_without_user_mode_still_clears_before_write() -> None:
    sent: list[bytes] = []

    def writer(report: bytes) -> int:
        sent.append(bytes(report))
        return len(report)

    kb = Ite8910KeyboardDevice(writer)
    kb.set_key_colors({(0, 0): (1, 2, 3)}, brightness=25, enable_user_mode=False)

    assert sent[0] == build_reset_report()
    assert sent[1] == build_brightness_speed_report_raw(0x05, 0x00)
    assert sent[2] == build_led_color_report(0x00, (1, 2, 3))


def test_backend_effect_builders_return_dict_payloads() -> None:
    backend = Ite8910Backend()
    wave_builder = backend.effects()["wave"]

    payload = wave_builder(speed=4, brightness=25)
    assert payload == {"name": "wave", "speed": 4, "brightness": 25}
    assert "rainbow" in backend.effects()
    assert "ripple" not in backend.effects()
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED


def test_backend_get_device_returns_keyboard_when_experimental_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTransport:
        def __init__(self):
            self.sent: list[bytes] = []

        def send_feature_report(self, report: bytes) -> int:
            self.sent.append(bytes(report))
            return len(report)

    transport = FakeTransport()
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "src.core.backends.ite8910.backend.open_matching_hidraw_transport",
        lambda *_a, **_k: (transport, SimpleNamespace(devnode="/dev/hidraw7")),
    )

    backend = Ite8910Backend()
    kb = backend.get_device()
    assert isinstance(kb, Ite8910KeyboardDevice)
    kb.set_brightness(25)
    assert transport.sent[0] == build_brightness_speed_report_raw(0x05, 0x00)


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
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
    assert res.available is False
    assert res.identifiers["usb_vid"] == "0x048d"
    assert res.identifiers["usb_pid"] == "0x8910"
    assert "experimental backend disabled" in (res.reason or "")


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
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