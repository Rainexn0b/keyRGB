from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.backends.sysfs import SysfsLedsBackend


def _make_led(tmp_path: Path, name: str, *, brightness: int, max_brightness: int) -> Path:
    led_dir = tmp_path / "class" / "leds" / name
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text(f"{brightness}\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text(f"{max_brightness}\n", encoding="utf-8")
    return led_dir


def test_sysfs_backend_probe_and_brightness_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _make_led(tmp_path, "tongfang::kbd_backlight", brightness=10, max_brightness=100)

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    # Pretend permissions are fine (CI tmp dirs are writable, but be explicit).
    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True
    assert probe.confidence >= 80

    dev = backend.get_device()

    # Read brightness mapped to 0..50 scale
    b = dev.get_brightness()
    assert 0 <= b <= 50

    dev.set_brightness(25)
    # Verify sysfs brightness updated
    brightness_path = Path(probe.identifiers["brightness"])
    assert brightness_path.read_text(encoding="utf-8").strip() != "10"


def test_sysfs_backend_probe_unavailable_when_no_leds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "class" / "leds").mkdir(parents=True)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is False


def test_sysfs_backend_prefers_multicolor_led(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plain = _make_led(tmp_path, "white:kbd_backlight", brightness=1, max_brightness=10)
    rgb = _make_led(tmp_path, "rgb:kbd_backlight", brightness=1, max_brightness=10)
    (rgb / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True

    brightness_path = Path(probe.identifiers["brightness"])
    assert str(brightness_path).startswith(str(rgb))

    # Sanity: the plain candidate exists but should not be selected.
    assert (plain / "brightness").exists()


def test_sysfs_backend_ignores_noise_lock_leds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    good = _make_led(tmp_path, "white:kbd_backlight", brightness=1, max_brightness=10)
    caps = _make_led(tmp_path, "white:kbd_backlight:capslock", brightness=1, max_brightness=10)
    num = _make_led(tmp_path, "white:kbd_backlight:numlock", brightness=1, max_brightness=10)

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True

    brightness_path = Path(probe.identifiers["brightness"])
    assert str(brightness_path).startswith(str(good))

    # Sanity: noise candidates exist but should not be selected.
    assert (caps / "brightness").exists()
    assert (num / "brightness").exists()


def test_sysfs_backend_is_deterministic_on_ties(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = _make_led(tmp_path, "a::kbd_backlight", brightness=1, max_brightness=10)
    b = _make_led(tmp_path, "b::kbd_backlight", brightness=1, max_brightness=10)

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True

    brightness_path = Path(probe.identifiers["brightness"])
    assert str(brightness_path).startswith(str(a))

    # Sanity: both candidates exist and are equally viable.
    assert (b / "brightness").exists()
