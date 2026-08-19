from __future__ import annotations

import logging
from threading import RLock

import pytest

from keyrgb.core.backends.ite8291r3_perkey import protocol
from keyrgb.core.backends.ite8291r3_perkey.backend import Ite8291r3Backend
from keyrgb.core.backends.ite8291r3_perkey.device import Ite8291r3KeyboardDevice
from keyrgb.core.effects.hw_payloads import allowed_hw_effect_keys, build_hw_effect_payload


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


def test_report_delay_env_helper_defaults_to_validated_025_ms(monkeypatch) -> None:
    from keyrgb.core.backends.ite8291r3_perkey.backend import _report_delay_s_from_env

    monkeypatch.delenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", raising=False)
    monkeypatch.delenv("KEYRGB_HID_REPORT_DELAY_MS", raising=False)
    assert _report_delay_s_from_env() == 0.00025


def test_report_delay_env_helper_parses_ms(monkeypatch) -> None:
    from keyrgb.core.backends.ite8291r3_perkey.backend import _report_delay_s_from_env

    monkeypatch.setenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", "2.5")
    assert _report_delay_s_from_env() == 0.0025


def test_report_delay_env_helper_allows_zero_to_disable(monkeypatch) -> None:
    from keyrgb.core.backends.ite8291r3_perkey.backend import _report_delay_s_from_env

    monkeypatch.setenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", "0")
    assert _report_delay_s_from_env() == 0.0


def test_report_delay_env_helper_falls_back_to_global(monkeypatch) -> None:
    from keyrgb.core.backends.ite8291r3_perkey.backend import _report_delay_s_from_env

    monkeypatch.delenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", raising=False)
    monkeypatch.setenv("KEYRGB_HID_REPORT_DELAY_MS", "4")
    assert _report_delay_s_from_env() == 0.004


def test_device_applies_report_delay_between_reports(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("keyrgb.core.backends._report_pacing.time.sleep", sleeps.append)

    controls: list[bytes] = []
    rows: list[bytes] = []
    device = Ite8291r3KeyboardDevice(
        controls.append,
        lambda _length: bytes(8),
        rows.append,
        report_delay_s=0.005,
    )

    device.set_color((0, 0, 0), brightness=25)

    # enable_user_mode (1) + set_row_index per row (6) + write_row per row (6)
    assert len(sleeps) == 13
    assert all(abs(s - 0.005) < 1e-9 for s in sleeps)


def test_coerce_helpers_reject_invalid_inputs() -> None:
    from keyrgb.core.backends.ite8291r3_perkey import device as device_mod

    with pytest.raises(ValueError, match="RGB 3-tuple"):
        device_mod._coerce_rgb(object())

    with pytest.raises(ValueError, match="tuple key ids"):
        device_mod._coerce_row_col((1, 2, 3))

    assert device_mod._coerce_row_col("bad") is None
    assert device_mod._coerce_row_col("x,y") is None
    assert device_mod._coerce_row_col("99,0") is None
    assert device_mod._coerce_row_col("0,99") is None
    assert device_mod._coerce_row_col("1,2") == (1, 2)
    assert device_mod._coerce_row_col((2, 3)) == (2, 3)


def test_coerce_effect_payload_from_name_dict_and_list() -> None:
    from keyrgb.core.backends.ite8291r3_perkey import device as device_mod

    named = device_mod._coerce_effect_payload({"name": "wave", "speed": 3, "brightness": 20})
    assert named[0] == protocol.effects["wave"](speed=3, brightness=20)[0]
    assert named[1] == 3
    assert named[2] == 20

    indexed = device_mod._coerce_effect_payload({"effect": 4, "speed": 2, "brightness": 10, "color": 1})
    assert indexed == (4, 2, 10, 1, 0, 0)

    listed = device_mod._coerce_effect_payload([7, 1, 2])
    assert listed == (7, 1, 2)

    with pytest.raises(ValueError, match="at most 6"):
        device_mod._coerce_effect_payload([1, 2, 3, 4, 5, 6, 7])

    with pytest.raises(ValueError, match="must contain"):
        device_mod._coerce_effect_payload({"speed": 1})

    with pytest.raises(ValueError, match="dict, list, or tuple"):
        device_mod._coerce_effect_payload("wave")


def test_device_constructor_requires_callables() -> None:
    with pytest.raises(TypeError, match="send_control_report"):
        Ite8291r3KeyboardDevice(None, lambda _n: b"", lambda _b: 0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="read_control_report"):
        Ite8291r3KeyboardDevice(lambda _b: 0, None, lambda _b: 0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="write_row_data"):
        Ite8291r3KeyboardDevice(lambda _b: 0, lambda _n: b"", None)  # type: ignore[arg-type]


def test_device_control_and_row_errors_and_fw_version() -> None:
    def fail_send(_report: bytes) -> int:
        return -1

    device = Ite8291r3KeyboardDevice(fail_send, lambda _n: bytes(8), lambda _b: 0, report_delay_s=0.0)
    with pytest.raises(OSError, match="control report"):
        device.set_brightness(10)

    def fail_row(_payload: bytes) -> int:
        return -1

    device = Ite8291r3KeyboardDevice(lambda _b: 0, lambda _n: bytes(8), fail_row, report_delay_s=0.0)
    with pytest.raises(OSError, match="row data"):
        device._write_row(b"\x00" * 8)

    controls: list[bytes] = []

    def read_fw(_length: int) -> bytes:
        return bytes((0x80, 1, 2, 3, 4, 0, 0, 0))

    device = Ite8291r3KeyboardDevice(controls.append, read_fw, lambda _b: 0, report_delay_s=0.0)
    assert device.get_fw_version() == (1, 2, 3, 4)
    assert controls == [protocol.build_get_fw_version_report()]


def test_device_effect_brightness_off_and_freeze() -> None:
    controls: list[bytes] = []
    effect_bytes = bytes((0x88, 0x02, 0x03, 0x04, 0x19, 0x01, 0x00, 0x00))

    def read_control(_length: int) -> bytes:
        return effect_bytes

    device = Ite8291r3KeyboardDevice(controls.append, read_control, lambda _b: 0, report_delay_s=0.0)

    device.set_effect({"name": "wave", "speed": 4, "brightness": 20})
    device.set_effect((1, 2, 3))
    device.set_brightness(50)
    device.turn_off()
    assert device.is_off() is False
    assert device.get_brightness() == 0x19

    before = len(controls)
    device.freeze()
    # freeze reads effect then writes set_effect with speed=11
    assert len(controls) > before


def test_device_set_key_colors_and_test_pattern_and_palette_restore() -> None:
    controls: list[bytes] = []
    rows: list[bytes] = []
    effect_bytes = bytes((0x88, 0x02, 0x00, 0x00, 0x19, 0x00, 0x00, 0x00))
    device = Ite8291r3KeyboardDevice(
        controls.append,
        lambda _n: effect_bytes,
        rows.append,
        report_delay_s=0.0,
    )

    device.set_key_colors(
        {
            (0, 0): (255, 0, 0),
            "1,2": (0, 255, 0),
            "bad": (1, 1, 1),
            (99, 0): (2, 2, 2),
        },
        brightness=30,
        save=False,
    )
    assert any(c == protocol.build_set_row_index_report(0) for c in controls)
    assert rows  # at least one row write

    rows.clear()
    controls.clear()
    device.test_pattern(shift=1, brightness=20, save=False)
    assert len(rows) == protocol.NUM_ROWS

    with pytest.raises(ValueError, match="palette color index"):
        device.set_palette_color(0, (1, 2, 3))

    controls.clear()
    device.restore_default_palette()
    assert len(controls) == len(protocol.DEFAULT_PALETTE)


def test_device_close_releases_transport() -> None:
    closed: list[str] = []

    class _Transport:
        def close(self) -> None:
            closed.append("closed")

    device = Ite8291r3KeyboardDevice(
        lambda _b: 0,
        lambda _n: bytes(8),
        lambda _b: 0,
        transport=_Transport(),  # type: ignore[arg-type]
        report_delay_s=0.0,
    )
    device.close()
    assert closed == ["closed"]
    assert device._transport is None

    # second close is a no-op
    device.close()


def test_device_close_swallows_transport_close_errors() -> None:
    class _BadTransport:
        def close(self) -> None:
            raise OSError("gone")

    device = Ite8291r3KeyboardDevice(
        lambda _b: 0,
        lambda _n: bytes(8),
        lambda _b: 0,
        transport=_BadTransport(),  # type: ignore[arg-type]
        report_delay_s=0.0,
    )
    device.close()
    assert device._transport is None


def test_device_set_key_colors_rewrites_all_rows_when_diff_disabled(monkeypatch) -> None:
    """Row diffing can be opted out via env; then every frame writes all rows."""
    monkeypatch.setenv("KEYRGB_ITE8291R3_SKIP_UNCHANGED_ROWS", "0")
    rows: list[bytes] = []
    device = Ite8291r3KeyboardDevice(lambda _b: 0, lambda _n: bytes(8), rows.append, report_delay_s=0.0)

    color_map = {(r, c): (r, c, 0) for r in range(protocol.NUM_ROWS) for c in range(protocol.NUM_COLS)}
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)

    assert len(rows) == 2 * protocol.NUM_ROWS


def test_device_set_key_colors_skips_unchanged_rows_by_default(monkeypatch) -> None:
    """Row diffing is default-on (hardware-validated); no env var needed."""
    monkeypatch.delenv("KEYRGB_ITE8291R3_SKIP_UNCHANGED_ROWS", raising=False)
    rows: list[bytes] = []
    device = Ite8291r3KeyboardDevice(lambda _b: 0, lambda _n: bytes(8), rows.append, report_delay_s=0.0)

    color_map = {(r, c): (r, c, 0) for r in range(protocol.NUM_ROWS) for c in range(protocol.NUM_COLS)}
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)
    assert len(rows) == protocol.NUM_ROWS

    # Identical frame: nothing to write.
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)
    assert len(rows) == protocol.NUM_ROWS

    # One changed key -> only that row is rewritten.
    changed = dict(color_map)
    changed[(2, 5)] = (255, 255, 255)
    device.set_key_colors(changed, brightness=30, enable_user_mode=False)
    assert len(rows) == protocol.NUM_ROWS + 1


def test_device_set_color_invalidates_row_diff_cache(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_ITE8291R3_SKIP_UNCHANGED_ROWS", "1")
    rows: list[bytes] = []
    effect_bytes = bytes((0x88, 0x02, 0x00, 0x00, 0x19, 0x00, 0x00, 0x00))
    device = Ite8291r3KeyboardDevice(lambda _b: 0, lambda _n: effect_bytes, rows.append, report_delay_s=0.0)

    color_map = {(r, c): (r, c, 0) for r in range(protocol.NUM_ROWS) for c in range(protocol.NUM_COLS)}
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)
    assert len(rows) == protocol.NUM_ROWS

    # set_color writes uniform rows through the same transport; the diff cache
    # must be invalidated so the next set_key_colors rewrites every row even if
    # its payload matches the pre-set_color frame.
    device.set_color((10, 20, 30), brightness=30)
    device.set_key_colors(color_map, brightness=30, enable_user_mode=False)
    assert len(rows) == 3 * protocol.NUM_ROWS


def test_report_delay_default_is_hardware_validated_025ms(monkeypatch) -> None:
    """No env vars -> the r3 backend uses its validated 0.25 ms pacing default."""
    from keyrgb.core.backends.ite8291r3_perkey.backend import _report_delay_s_from_env

    monkeypatch.delenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", raising=False)
    monkeypatch.delenv("KEYRGB_HID_REPORT_DELAY_MS", raising=False)
    assert _report_delay_s_from_env() == 0.00025

    monkeypatch.setenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS", "1.5")
    assert _report_delay_s_from_env() == 0.0015

    monkeypatch.delenv("KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS")
    monkeypatch.setenv("KEYRGB_HID_REPORT_DELAY_MS", "0")
    assert _report_delay_s_from_env() == 0.0
