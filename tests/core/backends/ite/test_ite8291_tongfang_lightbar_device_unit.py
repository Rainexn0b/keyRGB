from __future__ import annotations

import pytest

from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang import (
    protocol as tongfang_protocol,
)
from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.device import (
    Ite8291TongfangLightbarDevice,
)


def _make_device(
    features: list[bytes],
    outputs: list[bytes],
    **kwargs,
):
    def send_feature(report: bytes) -> int:
        features.append(bytes(report))
        return len(report)

    def write_output(report: bytes) -> int:
        outputs.append(bytes(report))
        return len(report)

    return Ite8291TongfangLightbarDevice(send_feature, write_output, **kwargs)


def test_tongfang_lightbar_device_requires_both_writers() -> None:
    with pytest.raises(TypeError, match="send_feature_report"):
        Ite8291TongfangLightbarDevice(None, lambda report: len(report))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="write_output_report"):
        Ite8291TongfangLightbarDevice(lambda report: len(report), None)  # type: ignore[arg-type]


def test_tongfang_lightbar_device_rejects_unknown_product_id() -> None:
    with pytest.raises(ValueError, match="0xce00"):
        _make_device([], [], product_id=0xCE00)


def test_tongfang_lightbar_device_set_color_sends_direct_sequence_in_order() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert features == [
        bytes((0x00, 0x08, 0x02, 0x33, 0x00, 0x19, 0x08, 0x00, 0x00)),
        bytes((0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((0x00, 0x12, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00)),
    ]
    assert len(outputs) == 1
    assert len(outputs[0]) == 65
    assert outputs[0][0] == 0x00
    assert outputs[0][1:4] == bytes((0x12, 0x56, 0x34))
    assert outputs[0][64] == 0x00
    assert device.is_off() is False
    assert device.get_brightness() == 25


def test_tongfang_lightbar_device_preserves_raw_rgb_without_software_scaling() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_color((0x20, 0x40, 0x60), brightness=25)

    # Raw channels preserved (R,B,G order); brightness rides the mode report.
    assert outputs[0][1:4] == bytes((0x20, 0x60, 0x40))
    assert features[0][5] == 25


def test_tongfang_lightbar_device_set_brightness_reuses_current_color() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_color((0x12, 0x34, 0x56), brightness=10)
    device.set_brightness(40)

    assert len(outputs) == 2
    assert outputs[1][1:4] == bytes((0x12, 0x56, 0x34))
    assert features[-3][5] == 40
    assert device.get_brightness() == 40


def test_tongfang_lightbar_device_turn_off_sends_off_report() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.turn_off()

    assert features == [bytes((0x00, 0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))]
    assert outputs == []
    assert device.is_off() is True
    assert device.get_brightness() == 0


def test_tongfang_lightbar_device_zero_brightness_turns_off() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_color((0x12, 0x34, 0x56), brightness=0)

    assert features == [tongfang_protocol.build_off_report()]
    assert outputs == []
    assert device.is_off() is True


def test_tongfang_lightbar_device_set_key_colors_collapses_to_average() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_key_colors({(0, 0): (200, 100, 50), (0, 1): (100, 200, 150)}, brightness=20)

    # Average (150, 150, 100) preserved raw in R,B,G order.
    assert outputs[0][1:4] == bytes((150, 100, 150))
    assert features[0][5] == 20
    assert device.get_brightness() == 20


def test_tongfang_lightbar_device_breathing_effect_sends_mode_then_seven_slots() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 5})

    assert len(features) == 8
    assert len(outputs) == 0
    assert features[0] == bytes((0x00, 0x08, 0x02, 0x02, 0x05, 0x19, 0x08, 0x00, 0x00))
    assert features[1:] == list(tongfang_protocol.build_effect_color_reports((0x12, 0x34, 0x56)))
    assert device.is_off() is False


def test_tongfang_lightbar_device_wave_effect() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_effect({"name": "wave", "color": (0x01, 0x02, 0x03), "brightness": 50, "speed": 10})

    assert len(features) == 8
    assert features[0] == bytes((0x00, 0x08, 0x02, 0x20, 0x0A, 0x32, 0x08, 0x00, 0x00))


def test_tongfang_lightbar_device_raindrops_effect() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_effect({"name": "raindrops", "color": (0x01, 0x02, 0x03), "brightness": 30, "speed": 4})

    assert len(features) == 8
    assert features[0] == bytes((0x00, 0x08, 0x02, 0x0A, 0x04, 0x1E, 0x08, 0x00, 0x00))


def test_tongfang_lightbar_device_rejects_unknown_effect() -> None:
    device = _make_device([], [])

    with pytest.raises(RuntimeError, match="Unsupported"):
        device.set_effect({"name": "rainbow"})


def test_tongfang_lightbar_device_sends_no_save_report() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []
    device = _make_device(features, outputs)

    device.set_color((0x12, 0x34, 0x56), brightness=25)
    device.set_brightness(30)
    device.set_effect({"name": "breathing", "color": (0x12, 0x34, 0x56), "brightness": 25, "speed": 5})
    device.turn_off()

    # Direct uniform: 3 feature writes + 1 output write each; effects: 8
    # feature writes; off: 1 feature write. No persistence/save traffic.
    assert len(features) == (3 + 3 + 8 + 1)
    assert len(outputs) == 2
    assert not hasattr(tongfang_protocol, "build_save_report")


def test_tongfang_lightbar_device_close_is_best_effort() -> None:
    features: list[bytes] = []
    outputs: list[bytes] = []

    class FlakyTransport:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True
            raise OSError("already gone")

    transport = FlakyTransport()
    device = _make_device(features, outputs, transport=transport)

    device.close()

    assert transport.closed is True
    # Second close is a safe no-op.
    device.close()


def test_tongfang_lightbar_device_close_without_transport() -> None:
    device = _make_device([], [])

    device.close()
