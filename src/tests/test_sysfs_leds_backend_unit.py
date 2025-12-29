from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.backends.sysfs_leds import SysfsLedsBackend


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
