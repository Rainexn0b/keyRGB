from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.backends.sysfs_mouse.backend import SysfsMouseBackend


def _make_led(tmp_path: Path, name: str, *, brightness: int, max_brightness: int) -> Path:
    led_dir = tmp_path / "class" / "leds" / name
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text(f"{brightness}\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text(f"{max_brightness}\n", encoding="utf-8")
    return led_dir


def _write_device_name(led_dir: Path, device_name: str) -> None:
    device_dir = led_dir / "device"
    device_dir.mkdir(parents=True, exist_ok=True)
    (device_dir / "name").write_text(device_name + "\n", encoding="utf-8")


def test_sysfs_mouse_backend_probe_and_device_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    backend = SysfsMouseBackend()
    probe = backend.probe()

    assert probe.available is True
    assert probe.identifiers["device_type"] == "mouse"
    assert probe.identifiers["context_key"] == "mouse:sysfs:usbmouse__rgb"

    device = backend.get_device()

    assert device.capabilities().per_key is False
    assert device.capabilities().color is True

    device.set_color((1, 2, 3), brightness=25)
    assert (led_dir / "multi_intensity").read_text(encoding="utf-8") == "1 2 3\n"


def test_sysfs_mouse_backend_stays_fail_closed_until_experimental_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    backend = SysfsMouseBackend()
    probe = backend.probe()

    assert probe.available is False
    assert "experimental backend disabled" in str(probe.reason).lower()


def test_sysfs_mouse_backend_accepts_metadata_backed_mouse_led_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "steelseries::logo", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")
    _write_device_name(led_dir, "SteelSeries Rival 3 Mouse")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    probe = SysfsMouseBackend().probe()

    assert probe.available is True
    assert probe.identifiers["led"] == "steelseries::logo"


def test_sysfs_mouse_backend_dimensions_are_always_single_zone() -> None:
    backend = SysfsMouseBackend()

    assert backend.dimensions() == (1, 1)


def test_sysfs_mouse_backend_set_color_with_color_attr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "color").write_text("000000\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    device = SysfsMouseBackend().get_device()
    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert (led_dir / "color").read_text(encoding="utf-8").strip() == "123456"


def test_sysfs_mouse_backend_set_color_with_rgb_attr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "rgb").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    device = SysfsMouseBackend().get_device()
    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert (led_dir / "rgb").read_text(encoding="utf-8").strip() == "18 52 86"


def test_sysfs_mouse_backend_set_brightness_scales_to_max_brightness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    device = SysfsMouseBackend().get_device()
    device.set_brightness(25)

    # 25/50 * 100 = 50
    assert (led_dir / "brightness").read_text(encoding="utf-8").strip() == "50"


def test_sysfs_mouse_backend_multi_zone_set_key_colors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    left = _make_led(tmp_path, "usbmouse:left:rgb", brightness=10, max_brightness=100)
    right = _make_led(tmp_path, "usbmouse:right:rgb", brightness=10, max_brightness=100)
    (left / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")
    (right / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    backend = SysfsMouseBackend()
    device = backend.get_device()

    # The backend picks the highest-scored LED as primary, so we exercise
    # set_key_colors by mapping keys to the underlying zones directly.
    device._zones = [
        {"led_dir": left, "type": "multi_intensity", "multi_index": ("red", "green", "blue")},
        {"led_dir": right, "type": "multi_intensity", "multi_index": ("red", "green", "blue")},
    ]
    device._key_to_zone_idx = {"esc": 0, "f1": 1}

    device.set_key_colors({"esc": (255, 0, 0), "f1": (0, 128, 255)}, brightness=50)

    assert (left / "multi_intensity").read_text(encoding="utf-8").strip() == "255 0 0"
    assert (right / "multi_intensity").read_text(encoding="utf-8").strip() == "0 128 255"


def test_sysfs_mouse_backend_probe_uses_helper_when_not_writable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "usbmouse::rgb", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda path, mode: mode == os.R_OK)

    import src.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_can_apply_led", lambda _led, color_kind=None: True)
    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: True)

    probe = SysfsMouseBackend().probe()

    assert probe.available is True
    assert "using helper" in (probe.reason or "").lower()
    assert probe.identifiers["helper_led_supported"] == "true"