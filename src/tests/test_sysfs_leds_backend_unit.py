from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.backends.sysfs import SysfsLedsBackend
from src.core.backends.sysfs.device import SysfsLedKeyboardDevice
from src.core.backends.sysfs.common import _leds_root, _safe_write_text


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


def test_leds_root_defaults_to_nonexistent_under_pytest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_SYSFS_LEDS_ROOT", raising=False)
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)

    root = _leds_root()
    assert str(root).endswith("/nonexistent-keyrgb-test-sysfs-leds")


def test_safe_write_text_tripwire_refuses_real_sysfs_under_pytest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.setenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", "1")

    with pytest.raises(RuntimeError):
        _safe_write_text(Path("/sys/class/leds/keyrgb-test/brightness"), "1\n")


def test_safe_write_text_is_noop_for_real_sysfs_without_tripwire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.delenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", raising=False)

    # Should not raise (and should not attempt to write).
    _safe_write_text(Path("/sys/class/leds/keyrgb-test/brightness"), "1\n")


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


def test_sysfs_backend_probe_reports_permission_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led = _make_led(tmp_path, "tongfang::kbd_backlight", brightness=1, max_brightness=10)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    # Pretend helper does NOT support LED apply for this test.
    import src.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: False)

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        p = str(path)
        if p.endswith(str(led / "brightness")) and mode == os.R_OK:
            return False
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is False
    assert "not readable" in (probe.reason or "")

    def fake_access_w(path: str | os.PathLike[str], mode: int) -> bool:
        p = str(path)
        if p.endswith(str(led / "brightness")) and mode == os.W_OK:
            return False
        return True

    monkeypatch.setattr(os, "access", fake_access_w)

    probe2 = backend.probe()
    assert probe2.available is False
    assert "not writable" in (probe2.reason or "")


def test_sysfs_backend_probe_allows_helper_when_not_writable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _make_led(tmp_path, "rgb:kbd_backlight", brightness=1, max_brightness=10)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    # Readable but not writable.
    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        if mode == os.R_OK:
            return True
        if mode == os.W_OK:
            return False
        return False

    monkeypatch.setattr(os, "access", fake_access)

    # Pretend helper supports LED apply.
    import src.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: True)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True
    assert probe.confidence >= 60
    assert "helper" in (probe.reason or "").lower()


def test_sysfs_backend_api_methods_are_stable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "class" / "leds").mkdir(parents=True)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    backend = SysfsLedsBackend()
    assert backend.is_available() is False
    assert backend.capabilities().per_key is False
    assert backend.dimensions() == (6, 21)
    assert backend.effects() == {}
    assert backend.colors() == {}

    with pytest.raises(FileNotFoundError):
        backend.get_device()
