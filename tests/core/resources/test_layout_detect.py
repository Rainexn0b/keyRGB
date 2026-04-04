from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import src.core.resources.layouts.detect as detect_mod
from src.core.resources.layouts.detect import detect_physical_layout


def test_detect_iso_when_key_102nd_present(tmp_path):
    """A sysfs device with KEY_A (30) and KEY_102ND (86) → iso."""
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    # bit 30 (KEY_A) and bit 86 (KEY_102ND) set in a 64-bit-word bitmap.
    # word1 (bits 64..127): bit 86-64=22 → 0x400000
    # word0 (bits 0..63):  bit 30 → 0x40000000
    caps.write_text("400000 40000000\n")

    with patch("src.core.resources.layouts.detect.glob.glob", return_value=[str(caps)]):
        assert detect_physical_layout() == "iso"


def test_detect_ansi_when_key_102nd_absent(tmp_path):
    """A sysfs device with KEY_A but without KEY_102ND → ansi."""
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    # Only KEY_A (bit 30) set.
    caps.write_text("0 40000000\n")

    with patch("src.core.resources.layouts.detect.glob.glob", return_value=[str(caps)]):
        assert detect_physical_layout() == "ansi"


def test_detect_auto_when_no_keyboard(tmp_path):
    """No device with letter keys → auto (inconclusive)."""
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    # Only power button codes, no KEY_A.
    caps.write_text("0 1\n")

    with patch("src.core.resources.layouts.detect.glob.glob", return_value=[str(caps)]):
        assert detect_physical_layout() == "auto"


def test_detect_auto_when_no_devices():
    """No sysfs devices at all → auto."""
    with patch("src.core.resources.layouts.detect.glob.glob", return_value=[]):
        assert detect_physical_layout() == "auto"


def test_detect_auto_when_only_generic_at_keyboard_reports_key_102nd(tmp_path):
    """A generic AT node advertising KEY_102ND is treated as inconclusive."""
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    (tmp_path / "input0" / "name").write_text("AT Translated Set 2 keyboard\n")
    caps.write_text("400000 40000000\n")

    with patch("src.core.resources.layouts.detect.glob.glob", return_value=[str(caps)]):
        assert detect_physical_layout() == "auto"


def test_device_name_for_cap_path_uses_device_name_fallback(tmp_path) -> None:
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    (tmp_path / "input0" / "name").write_text("\n")
    device_name = tmp_path / "input0" / "device" / "name"
    device_name.parent.mkdir(parents=True)
    device_name.write_text("USB Keyboard\n")

    assert detect_mod._device_name_for_cap_path(str(caps)) == "USB Keyboard"


def test_device_name_for_cap_path_uses_device_name_fallback_when_primary_name_is_unreadable(
    tmp_path, monkeypatch
) -> None:
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)
    primary_name = tmp_path / "input0" / "name"
    device_name = tmp_path / "input0" / "device" / "name"
    device_name.parent.mkdir(parents=True)
    device_name.write_text("USB Keyboard\n")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if self == primary_name:
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert detect_mod._device_name_for_cap_path(str(caps)) == "USB Keyboard"


def test_device_name_for_cap_path_returns_empty_when_names_unreadable(tmp_path, monkeypatch) -> None:
    caps = tmp_path / "input0" / "capabilities" / "key"
    caps.parent.mkdir(parents=True)

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert detect_mod._device_name_for_cap_path(str(caps)) == ""


def test_is_generic_at_keyboard_normalizes_case_and_whitespace() -> None:
    assert detect_mod._is_generic_at_keyboard("  AT Translated Set 2 Keyboard  ") is True
    assert detect_mod._is_generic_at_keyboard("USB Keyboard") is False


def test_detect_layout_skips_unreadable_and_blank_capability_files(tmp_path, monkeypatch) -> None:
    unreadable = tmp_path / "input0" / "capabilities" / "key"
    blank = tmp_path / "input1" / "capabilities" / "key"
    ansi = tmp_path / "input2" / "capabilities" / "key"

    unreadable.parent.mkdir(parents=True)
    blank.parent.mkdir(parents=True)
    ansi.parent.mkdir(parents=True)
    blank.write_text("\n")
    ansi.write_text("0 40000000\n")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if self == unreadable:
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    with patch(
        "src.core.resources.layouts.detect.glob.glob",
        return_value=[str(unreadable), str(blank), str(ansi)],
    ):
        assert detect_physical_layout() == "ansi"
