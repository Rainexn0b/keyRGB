from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.backends.sysfs.common import _write_int
from keyrgb.core.backends.sysfs.device import SysfsLedKeyboardDevice


def _make_led(tmp_path: Path, name: str, *, brightness: int, max_brightness: int) -> Path:
    led_dir = tmp_path / "class" / "leds" / name
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text(f"{brightness}\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text(f"{max_brightness}\n", encoding="utf-8")
    return led_dir


def test_write_int_ignores_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.common.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    _write_int(tmp_path / "brightness", 7)

    assert (tmp_path / "brightness").read_text(encoding="utf-8") == "7\n"


def test_write_int_propagates_unexpected_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.common.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        _write_int(tmp_path / "brightness", 7)

    assert not (tmp_path / "brightness").exists()


def test_sysfs_device_set_brightness_ignores_recoverable_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    led_dir = _make_led(tmp_path, "rgb:kbd_backlight", brightness=0, max_brightness=100)
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    dev.set_brightness(25)

    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_brightness_propagates_unexpected_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    led_dir = _make_led(tmp_path, "rgb:kbd_backlight", brightness=0, max_brightness=100)
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        dev.set_brightness(25)

    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "0"


def test_sysfs_device_set_color_ignores_recoverable_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    led_dir = _make_led(tmp_path, "rgb::kbd_backlight", brightness=0, max_brightness=100)
    rgb = led_dir / "rgb"
    rgb.write_text("0 0 0\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    dev.set_color((4, 5, 6), brightness=25)

    assert rgb.read_text(encoding="utf-8") == "4 5 6\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_propagates_unexpected_debug_logging_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    led_dir = _make_led(tmp_path, "rgb::kbd_backlight", brightness=0, max_brightness=100)
    rgb = led_dir / "rgb"
    rgb.write_text("0 0 0\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.logger.info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        dev.set_color((4, 5, 6), brightness=25)

    assert rgb.read_text(encoding="utf-8") == "0 0 0\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "0"


def test_sysfs_device_set_color_multi_intensity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "rgb:kbd_backlight", brightness=0, max_brightness=100)
    multi = led_dir / "multi_intensity"
    multi.write_text("0 0 0\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(
        primary_led_dir=led_dir,
    )

    dev.set_color((1, 2, 3), brightness=25)

    assert multi.read_text(encoding="utf-8") == "1 2 3\n"
    # 25/50 of max(100) -> 50
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_multi_intensity_uses_multi_index_order(tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "rgb:kbd_backlight", brightness=0, max_brightness=100)
    multi = led_dir / "multi_intensity"
    multi.write_text("0 0 0\n", encoding="utf-8")
    (led_dir / "multi_index").write_text("blue green red\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    dev.set_color((1, 2, 3), brightness=25)

    assert multi.read_text(encoding="utf-8") == "3 2 1\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_multi_intensity_falls_back_for_unknown_multi_index(tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "rgb:kbd_backlight", brightness=0, max_brightness=100)
    multi = led_dir / "multi_intensity"
    multi.write_text("0 0 0\n", encoding="utf-8")
    (led_dir / "multi_index").write_text("amber red blue\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    dev.set_color((1, 2, 3), brightness=25)

    assert multi.read_text(encoding="utf-8") == "1 2 3\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_color_attr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "ite::kbd_backlight", brightness=0, max_brightness=100)
    color = led_dir / "color"
    color.write_text("000000\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(
        primary_led_dir=led_dir,
    )

    dev.set_color((1, 2, 3), brightness=25)

    assert color.read_text(encoding="utf-8") == "010203\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_ite8297_channel_triplet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    red = _make_led(tmp_path, "ite_8297:1", brightness=0, max_brightness=255)
    green = _make_led(tmp_path, "ite_8297:2", brightness=0, max_brightness=255)
    blue = _make_led(tmp_path, "ite_8297:3", brightness=0, max_brightness=255)

    dev = SysfsLedKeyboardDevice(
        primary_led_dir=red,
        all_led_dirs=[red, green, blue],
    )

    dev.set_color((100, 50, 25), brightness=25)

    assert (red / "brightness").read_text(encoding="utf-8").strip() == "50"
    assert (green / "brightness").read_text(encoding="utf-8").strip() == "25"
    assert (blue / "brightness").read_text(encoding="utf-8").strip() == "12"
    assert dev.get_brightness() == 25


def test_sysfs_device_brightness_updates_ite8297_channel_triplet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    red = _make_led(tmp_path, "ite_8297:1", brightness=100, max_brightness=255)
    green = _make_led(tmp_path, "ite_8297:2", brightness=50, max_brightness=255)
    blue = _make_led(tmp_path, "ite_8297:3", brightness=25, max_brightness=255)

    dev = SysfsLedKeyboardDevice(
        primary_led_dir=red,
        all_led_dirs=[red, green, blue],
    )

    dev.set_brightness(10)

    assert (red / "brightness").read_text(encoding="utf-8").strip() == "20"
    assert (green / "brightness").read_text(encoding="utf-8").strip() == "10"
    assert (blue / "brightness").read_text(encoding="utf-8").strip() == "5"
    assert dev.get_brightness() == 10


def test_sysfs_device_set_color_system76_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "system76::kbd_backlight", brightness=0, max_brightness=100)
    left = led_dir / "color_left"
    right = led_dir / "color_right"
    left.write_text("000000\n", encoding="utf-8")
    right.write_text("000000\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(
        primary_led_dir=led_dir,
    )

    dev.set_color((0xAB, 0xCD, 0xEF), brightness=25)

    assert left.read_text(encoding="utf-8") == "ABCDEF\n"
    assert right.read_text(encoding="utf-8") == "ABCDEF\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


@pytest.mark.parametrize("error_cls", [RuntimeError, ValueError])
def test_sysfs_device_channel_group_init_falls_back_when_state_read_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error_cls: type[Exception]
) -> None:
    red = _make_led(tmp_path, "ite_8297:1", brightness=0, max_brightness=255)
    green = _make_led(tmp_path, "ite_8297:2", brightness=0, max_brightness=255)
    blue = _make_led(tmp_path, "ite_8297:3", brightness=0, max_brightness=255)

    monkeypatch.setattr(
        SysfsLedKeyboardDevice,
        "_read_channel_group_state",
        lambda self, channels: (_ for _ in ()).throw(error_cls("boom")),
    )

    dev = SysfsLedKeyboardDevice(primary_led_dir=red, all_led_dirs=[red, green, blue])

    assert dev._channel_group_color == (0, 0, 0)
    assert dev._channel_group_brightness == 0


def test_sysfs_device_capabilities_detect_rgb_attr_and_handle_probe_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    led_dir = _make_led(tmp_path, "generic::kbd_backlight", brightness=1, max_brightness=10)
    (led_dir / "rgb").write_text("0 0 0\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    assert dev.capabilities().color is True

    monkeypatch.setattr(dev, "_supports_multicolor", lambda _led: (_ for _ in ()).throw(RuntimeError("bad")))
    assert dev.capabilities().color is False


@pytest.mark.parametrize("error_cls", [OSError, ValueError])
def test_sysfs_device_defensive_readers_and_power_state_helpers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error_cls: type[Exception]
) -> None:
    led_dir = _make_led(tmp_path, "generic::kbd_backlight", brightness=1, max_brightness=10)
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.common._read_int", lambda _path: (_ for _ in ()).throw(error_cls("nope"))
    )
    assert dev._max() == 1
    assert dev._read_sysfs_brightness() == 0

    calls: list[int] = []
    monkeypatch.setattr(dev, "set_brightness", lambda brightness: calls.append(int(brightness)))
    monkeypatch.setattr(dev, "get_brightness", lambda: 0)

    dev.turn_off()

    assert calls == [0]
    assert dev.is_off() is True


def test_sysfs_zone_brightness_uses_helper_or_raises_for_primary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    primary = _make_led(tmp_path, "primary::kbd_backlight", brightness=1, max_brightness=10)
    other = _make_led(tmp_path, "other::kbd_backlight", brightness=1, max_brightness=10)
    dev = SysfsLedKeyboardDevice(primary_led_dir=primary)

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.common._write_int",
        lambda _path, _value: (_ for _ in ()).throw(PermissionError("deny")),
    )
    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: False)

    with pytest.raises(PermissionError):
        dev._set_zone_brightness(primary, 5)

    assert dev._set_zone_brightness(other, 5) is None

    helper_calls: list[tuple[str, int, tuple[int, int, int] | None]] = []
    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: helper_calls.append((led, brightness, rgb)) or True,
    )

    assert dev._set_zone_brightness(primary, 7) is None
    assert helper_calls == [(primary.name, 7, None)]

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: False,
    )
    with pytest.raises(PermissionError):
        dev._set_zone_brightness(primary, 9)


def test_sysfs_device_set_color_rgb_attr_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "rgb::kbd_backlight", brightness=0, max_brightness=100)
    rgb = led_dir / "rgb"
    rgb.write_text("0 0 0\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    dev.set_color((4, 5, 6), brightness=25)

    assert rgb.read_text(encoding="utf-8") == "4 5 6\n"
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_device_set_color_file_zone_permission_error_raises_without_helper_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    led_dir = _make_led(tmp_path, "system76::kbd_backlight", brightness=0, max_brightness=100)
    file_path = led_dir / "color_left"
    file_path.write_text("000000\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    zone = {"type": "file", "path": file_path, "led_dir": led_dir}
    helper_calls: list[tuple[str, int, tuple[int, int, int] | None]] = []

    def fake_safe_write(path: Path, _content: str) -> None:
        if path == file_path:
            raise PermissionError("deny")
        path.write_text("unexpected\n", encoding="utf-8")

    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.common._safe_write_text", fake_safe_write)
    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: helper_calls.append((led, brightness, rgb)) or True,
    )

    with pytest.raises(PermissionError, match="sysfs color file not writable"):
        dev._set_zone_color(zone, (1, 2, 3), 25)

    assert helper_calls == []


def test_sysfs_device_set_color_helper_fallbacks_for_multi_and_color_attrs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    multi_led = _make_led(tmp_path, "multi::kbd_backlight", brightness=0, max_brightness=100)
    (multi_led / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")
    color_led = _make_led(tmp_path, "color::kbd_backlight", brightness=0, max_brightness=100)
    (color_led / "color").write_text("000000\n", encoding="utf-8")

    dev = SysfsLedKeyboardDevice(primary_led_dir=multi_led)
    calls: list[tuple[str, int, tuple[int, int, int] | None]] = []

    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.common._safe_write_text",
        lambda _path, _content: (_ for _ in ()).throw(PermissionError("deny")),
    )
    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: calls.append((led, brightness, rgb)) or True,
    )

    dev._set_zone_color({"type": "dir", "path": multi_led, "led_dir": multi_led}, (10, 20, 30), 25)
    dev._set_zone_color({"type": "dir", "path": color_led, "led_dir": color_led}, (11, 22, 33), 30)

    assert calls == [
        (multi_led.name, 50, (10, 20, 30)),
        (color_led.name, 60, (11, 22, 33)),
    ]


def test_sysfs_device_set_color_rgb_attr_primary_failure_does_not_use_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    led_dir = _make_led(tmp_path, "rgb::kbd_backlight", brightness=0, max_brightness=100)
    rgb = led_dir / "rgb"
    rgb.write_text("0 0 0\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    helper_calls: list[tuple[str, int, tuple[int, int, int] | None]] = []

    def fake_safe_write(path: Path, _content: str) -> None:
        if path == rgb:
            raise PermissionError("deny")
        raise AssertionError(path)

    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.common._safe_write_text", fake_safe_write)
    monkeypatch.setattr("keyrgb.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "keyrgb.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: helper_calls.append((led, brightness, rgb)) or True,
    )

    with pytest.raises(PermissionError, match="sysfs rgb attribute not writable"):
        dev._set_zone_color({"type": "dir", "path": led_dir, "led_dir": led_dir}, (7, 8, 9), 25)

    assert helper_calls == []


def test_sysfs_device_set_key_colors_single_zone_and_multi_zone_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    single_led = _make_led(tmp_path, "single::kbd_backlight", brightness=0, max_brightness=100)
    single = SysfsLedKeyboardDevice(primary_led_dir=single_led)
    single_calls: list[tuple[tuple[int, int, int], int]] = []

    monkeypatch.setattr(
        single, "set_color", lambda color, *, brightness: single_calls.append((tuple(color), int(brightness)))
    )

    single.set_key_colors({}, brightness=25)
    single.set_key_colors({"a": (30, 0, 0), "b": (0, 60, 0), "c": (0, 0, 90)}, brightness=35)

    assert single_calls == [((10, 20, 30), 35)]

    left = _make_led(tmp_path, "left::kbd_backlight", brightness=0, max_brightness=100)
    right = _make_led(tmp_path, "right::kbd_backlight", brightness=0, max_brightness=100)
    multi = SysfsLedKeyboardDevice(primary_led_dir=left, all_led_dirs=[left, right])
    multi._key_to_zone_idx = {"esc": 0, "f1": 1, "f2": 1}
    zone_calls: list[tuple[dict, tuple[int, int, int], int]] = []

    monkeypatch.setattr(
        multi,
        "_set_zone_color",
        lambda zone, color, brightness: zone_calls.append((zone, tuple(color), int(brightness))),
    )

    multi.set_key_colors(
        {
            "esc": (10, 20, 30),
            "f1": (0, 100, 0),
            "f2": (0, 0, 50),
            "unknown": (255, 255, 255),
        },
        brightness=40,
    )

    assert zone_calls == [
        (multi._zones[0], (10, 20, 30), 40),
        (multi._zones[1], (0, 50, 25), 40),
    ]


def test_sysfs_device_set_effect_is_noop(tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "plain::kbd_backlight", brightness=0, max_brightness=100)
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    assert dev.set_effect({"name": "wave"}) is None
