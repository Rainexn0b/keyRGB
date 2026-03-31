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
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS


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


def test_sysfs_backend_detects_ite8297_channel_triplet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    red = _make_led(tmp_path, "ite_8297:1", brightness=10, max_brightness=255)
    _make_led(tmp_path, "ite_8297:2", brightness=20, max_brightness=255)
    _make_led(tmp_path, "ite_8297:3", brightness=30, max_brightness=255)

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        return True

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True
    assert probe.identifiers["led"].lower() == "ite_8297:1"
    assert probe.identifiers["supports_channel_rgb"] == "true"

    dev = backend.get_device()
    assert dev.capabilities().color is True
    assert dev.capabilities().per_key is False

    assert (red / "brightness").exists()


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


def test_sysfs_device_channel_group_init_falls_back_when_state_read_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    red = _make_led(tmp_path, "ite_8297:1", brightness=0, max_brightness=255)
    green = _make_led(tmp_path, "ite_8297:2", brightness=0, max_brightness=255)
    blue = _make_led(tmp_path, "ite_8297:3", brightness=0, max_brightness=255)

    monkeypatch.setattr(
        SysfsLedKeyboardDevice,
        "_read_channel_group_state",
        lambda self, channels: (_ for _ in ()).throw(RuntimeError("boom")),
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


def test_sysfs_device_defensive_readers_and_power_state_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "generic::kbd_backlight", brightness=1, max_brightness=10)
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    monkeypatch.setattr("src.core.backends.sysfs.device.common._read_int", lambda _path: (_ for _ in ()).throw(OSError("nope")))
    assert dev._max() == 1
    assert dev._read_sysfs_brightness() == 0

    calls: list[int] = []
    monkeypatch.setattr(dev, "set_brightness", lambda brightness: calls.append(int(brightness)))
    monkeypatch.setattr(dev, "get_brightness", lambda: 0)

    dev.turn_off()

    assert calls == [0]
    assert dev.is_off() is True


def test_sysfs_zone_brightness_uses_helper_or_raises_for_primary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    primary = _make_led(tmp_path, "primary::kbd_backlight", brightness=1, max_brightness=10)
    other = _make_led(tmp_path, "other::kbd_backlight", brightness=1, max_brightness=10)
    dev = SysfsLedKeyboardDevice(primary_led_dir=primary)

    monkeypatch.setattr(
        "src.core.backends.sysfs.device.common._write_int",
        lambda _path, _value: (_ for _ in ()).throw(PermissionError("deny")),
    )
    monkeypatch.setattr("src.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: False)

    with pytest.raises(PermissionError):
        dev._set_zone_brightness(primary, 5)

    assert dev._set_zone_brightness(other, 5) is None

    helper_calls: list[tuple[str, int, tuple[int, int, int] | None]] = []
    monkeypatch.setattr("src.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "src.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: helper_calls.append((led, brightness, rgb)) or True,
    )

    assert dev._set_zone_brightness(primary, 7) is None
    assert helper_calls == [(primary.name, 7, None)]

    monkeypatch.setattr(
        "src.core.backends.sysfs.device.privileged.run_led_apply",
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


def test_sysfs_device_set_color_file_zone_permission_error_falls_back_to_brightness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    led_dir = _make_led(tmp_path, "system76::kbd_backlight", brightness=0, max_brightness=100)
    file_path = led_dir / "color_left"
    file_path.write_text("000000\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)
    zone = {"type": "file", "path": file_path, "led_dir": led_dir}
    brightness_calls: list[int] = []

    def fake_safe_write(path: Path, _content: str) -> None:
        if path == file_path:
            raise PermissionError("deny")
        path.write_text("unexpected\n", encoding="utf-8")

    monkeypatch.setattr("src.core.backends.sysfs.device.common._safe_write_text", fake_safe_write)
    monkeypatch.setattr(dev, "_set_zone_brightness", lambda _led_dir, sysfs_value: brightness_calls.append(int(sysfs_value)))

    dev._set_zone_color(zone, (1, 2, 3), 25)

    assert brightness_calls == [50]


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
        "src.core.backends.sysfs.device.common._safe_write_text",
        lambda _path, _content: (_ for _ in ()).throw(PermissionError("deny")),
    )
    monkeypatch.setattr("src.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: True)
    monkeypatch.setattr(
        "src.core.backends.sysfs.device.privileged.run_led_apply",
        lambda *, led, brightness, rgb: calls.append((led, brightness, rgb)) or True,
    )

    dev._set_zone_color({"type": "dir", "path": multi_led, "led_dir": multi_led}, (10, 20, 30), 25)
    dev._set_zone_color({"type": "dir", "path": color_led, "led_dir": color_led}, (11, 22, 33), 30)

    assert calls == [
        (multi_led.name, 50, (10, 20, 30)),
        (color_led.name, 60, (11, 22, 33)),
    ]


def test_sysfs_device_set_color_rgb_attr_primary_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led_dir = _make_led(tmp_path, "rgb::kbd_backlight", brightness=0, max_brightness=100)
    rgb = led_dir / "rgb"
    rgb.write_text("0 0 0\n", encoding="utf-8")
    dev = SysfsLedKeyboardDevice(primary_led_dir=led_dir)

    def fake_safe_write(path: Path, _content: str) -> None:
        if path == rgb:
            raise PermissionError("deny")
        raise AssertionError(path)

    monkeypatch.setattr("src.core.backends.sysfs.device.common._safe_write_text", fake_safe_write)
    monkeypatch.setattr("src.core.backends.sysfs.device.privileged.helper_supports_led_apply", lambda: False)

    with pytest.raises(PermissionError):
        dev._set_zone_color({"type": "dir", "path": led_dir, "led_dir": led_dir}, (7, 8, 9), 25)


def test_sysfs_device_set_key_colors_single_zone_and_multi_zone_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    single_led = _make_led(tmp_path, "single::kbd_backlight", brightness=0, max_brightness=100)
    single = SysfsLedKeyboardDevice(primary_led_dir=single_led)
    single_calls: list[tuple[tuple[int, int, int], int]] = []

    monkeypatch.setattr(single, "set_color", lambda color, *, brightness: single_calls.append((tuple(color), int(brightness))))

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
    assert backend.dimensions() == (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)
    assert backend.effects() == {}
    assert backend.colors() == {}

    with pytest.raises(FileNotFoundError):
        backend.get_device()
