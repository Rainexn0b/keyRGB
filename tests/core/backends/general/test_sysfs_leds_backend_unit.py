from __future__ import annotations

import os
from pathlib import Path

import pytest

from keyrgb.core.backends.sysfs import SysfsLedsBackend
from keyrgb.core.backends.sysfs.common import _is_real_sysfs_path, _leds_root, _safe_write_text
from keyrgb.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


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


def test_sysfs_backend_probe_tolerates_led_enumeration_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenRoot:
        def exists(self) -> bool:
            return True

        def iterdir(self):
            raise PermissionError("denied")

    monkeypatch.setattr("keyrgb.core.backends.sysfs.backend.common._leds_root", lambda: _BrokenRoot())

    backend = SysfsLedsBackend()
    probe = backend.probe()

    assert probe.available is False
    assert probe.reason == "no matching sysfs LED"


def test_sysfs_backend_capabilities_tolerate_find_leds_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = SysfsLedsBackend()
    monkeypatch.setattr(backend, "_find_leds", lambda: (_ for _ in ()).throw(PermissionError("denied")))

    caps = backend.capabilities()

    assert caps.brightness is True
    assert caps.per_key is False
    assert caps.color is False


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


def test_safe_write_text_is_noop_when_access_tripwire_is_explicitly_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.setenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", "0")

    # Should not raise (and should not attempt to write).
    _safe_write_text(Path("/sys/class/leds/keyrgb-test/brightness"), "1\n")


def test_safe_write_text_refuses_real_sysfs_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.delenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", raising=False)

    with pytest.raises(RuntimeError, match="Refusing to write real sysfs"):
        _safe_write_text(Path("/sys/class/leds/keyrgb-test/brightness"), "1\n")


def test_is_real_sysfs_path_returns_false_when_resolution_fails_for_non_sysfs_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        os.path,
        "realpath",
        lambda _path: (_ for _ in ()).throw(OSError("boom")),
    )

    assert _is_real_sysfs_path(tmp_path / "brightness") is False


def test_sysfs_backend_probe_reports_permission_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    led = _make_led(tmp_path, "tongfang::kbd_backlight", brightness=1, max_brightness=10)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    # Pretend helper does NOT support LED apply for this test.
    import keyrgb.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: False)

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        p = str(path)
        return not (p.endswith(str(led / "brightness")) and mode == os.R_OK)

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is False
    assert "not readable" in (probe.reason or "")

    def fake_access_w(path: str | os.PathLike[str], mode: int) -> bool:
        p = str(path)
        return not (p.endswith(str(led / "brightness")) and mode == os.W_OK)

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
    import keyrgb.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: True)

    backend = SysfsLedsBackend()
    probe = backend.probe()
    assert probe.available is True
    assert probe.confidence >= 60


def test_sysfs_backend_probe_accepts_ite8297_via_helper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ITE 8297 channel LEDs are now accepted by the privileged helper."""
    _make_led(tmp_path, "ite_8297:1", brightness=1, max_brightness=255)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        if mode == os.R_OK:
            return True
        if mode == os.W_OK:
            return False
        return False

    monkeypatch.setattr(os, "access", fake_access)

    import keyrgb.core.backends.sysfs.privileged as sysfs_privileged

    monkeypatch.setattr(sysfs_privileged, "helper_supports_led_apply", lambda: True)

    backend = SysfsLedsBackend()
    probe = backend.probe()

    assert probe.available is True
    assert probe.identifiers["helper_led_supported"] == "true"
    assert "using helper" in (probe.reason or "").lower()


def test_sysfs_backend_probe_treats_access_oserror_as_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_led(tmp_path, "rgb:kbd_backlight", brightness=1, max_brightness=10)
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "class" / "leds"))

    def fake_access(_path: str | os.PathLike[str], _mode: int) -> bool:
        raise PermissionError("denied")

    monkeypatch.setattr(os, "access", fake_access)

    backend = SysfsLedsBackend()
    probe = backend.probe()

    assert probe.available is False
    assert probe.reason == "brightness not readable"
    assert probe.identifiers["brightness_readable"] == "false"
    assert probe.identifiers["brightness_writable"] == "false"


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
