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


def test_sysfs_mouse_backend_rejects_non_mouse_vendor_logo_led_without_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    led_dir = _make_led(tmp_path, "steelseries::logo", brightness=10, max_brightness=100)
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(os, "access", lambda _path, _mode: True)

    probe = SysfsMouseBackend().probe()

    assert probe.available is False
    assert probe.reason == "no matching sysfs mouse LED"