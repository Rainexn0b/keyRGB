from __future__ import annotations

import logging
from threading import RLock

from src.core.backends.ite8291r3 import protocol
from src.core.backends.ite8291r3.device import Ite8291r3KeyboardDevice
from src.core.backends.ite8291r3.backend import Ite8291r3Backend
from src.core.effects.hw_payloads import allowed_hw_effect_keys, build_hw_effect_payload


def test_protocol_effect_builder_uses_expected_defaults() -> None:
    payload = protocol.effects["wave"]()

    assert payload == [0x03, 5, 25, 0, 1, 0]


def test_protocol_effect_builders_expose_allowed_keys_via_closure() -> None:
    keys = allowed_hw_effect_keys(protocol.effects["breathing"], logger=logging.getLogger(__name__))

    assert keys == {"speed", "brightness", "color", "save"}


def test_backend_effect_payload_builder_still_inverts_speed_for_native_r3() -> None:
    captured_kwargs: dict[str, object] = {}

    def capture_effect(**kwargs: object) -> list[int]:
        captured_kwargs.update(kwargs)
        return [0x03, int(kwargs.get("speed", 0)), int(kwargs.get("brightness", 0)), 0, 1, 0]

    payload = build_hw_effect_payload(
        effect_name="wave",
        effect_func=capture_effect,
        ui_speed=10,
        brightness=50,
        current_color=(255, 255, 255),
        hw_colors={},
        kb=type("Kb", (), {"keyrgb_hw_speed_policy": "inverted"})(),
        kb_lock=RLock(),
        logger=logging.getLogger(__name__),
    )

    assert captured_kwargs["speed"] == 1
    assert payload[1] == 1


def test_device_set_color_uses_r3_row_layout_offsets() -> None:
    controls: list[bytes] = []
    rows: list[bytes] = []
    device = Ite8291r3KeyboardDevice(controls.append, lambda _length: bytes(8), rows.append)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert controls[0] == protocol.build_set_effect_report(
        control=0x02,
        effect=protocol.USER_MODE_EFFECT,
        speed=0,
        brightness=25,
        color=0,
        direction_or_reactive=0,
        save=0,
    )
    assert controls[1] == protocol.build_set_row_index_report(0)
    assert rows[0][0] == 0x00
    assert rows[0][1] == 0x56
    assert rows[0][22] == 0x34
    assert rows[0][43] == 0x12
    assert rows[0][64] == 0x00


def test_device_set_palette_color_builds_expected_control_report() -> None:
    controls: list[bytes] = []
    device = Ite8291r3KeyboardDevice(controls.append, lambda _length: bytes(8), lambda _payload: 0)

    device.set_palette_color(3, (0x12, 0x34, 0x56))

    assert controls == [protocol.build_set_palette_color_report(3, (0x12, 0x34, 0x56))]


def test_device_get_effect_reads_back_payload() -> None:
    controls: list[bytes] = []

    def read_control(_length: int) -> bytes:
        return bytes((protocol.Commands.GET_EFFECT, 0x02, 0x03, 0x04, 0x19, 0x01, 0x00, 0x00))

    device = Ite8291r3KeyboardDevice(controls.append, read_control, lambda _payload: 0)

    effect = device.get_effect()

    assert controls == [protocol.build_get_effect_report()]
    assert effect == [0x03, 0x04, 0x19, 0x01, 0x00, 0x00]


def test_backend_effects_and_colors_are_native_protocol_maps() -> None:
    backend = Ite8291r3Backend()
    effects = backend.effects()
    colors = backend.colors()

    assert set(effects) >= {"breathing", "wave", "random", "rainbow"}
    assert colors["red"] == 1
    assert colors["random"] == 8