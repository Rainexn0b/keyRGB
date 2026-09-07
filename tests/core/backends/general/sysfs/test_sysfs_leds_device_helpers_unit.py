from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.backends.sysfs.device import SysfsLedKeyboardDevice


def _make_led(tmp_path: Path, name: str, *, brightness: int, max_brightness: int) -> Path:
    led_dir = tmp_path / "class" / "leds" / name
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text(f"{brightness}\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text(f"{max_brightness}\n", encoding="utf-8")
    return led_dir


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
