from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.diagnostics import collect_diagnostics, format_diagnostics_text
from src.core.diagnostics.model import Diagnostics


def test_collect_diagnostics_reads_dmi_and_leds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Fake DMI
    dmi_root = tmp_path / "sys" / "class" / "dmi" / "id"
    dmi_root.mkdir(parents=True)
    (dmi_root / "sys_vendor").write_text("TONGFANG\n", encoding="utf-8")
    (dmi_root / "product_name").write_text("GM5\n", encoding="utf-8")

    # Fake LEDs
    leds_root = tmp_path / "sys" / "class" / "leds"
    (leds_root / "tongfang::kbd_backlight").mkdir(parents=True)
    (leds_root / "tongfang::kbd_backlight" / "brightness").write_text("1\n", encoding="utf-8")
    (leds_root / "tongfang::kbd_backlight" / "max_brightness").write_text("10\n", encoding="utf-8")
    (leds_root / "input3::capslock").mkdir(parents=True)
    (leds_root / "input3::capslock" / "brightness").write_text("0\n", encoding="utf-8")
    (leds_root / "input3::capslock" / "max_brightness").write_text("1\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_DMI_ROOT", str(dmi_root))
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(leds_root))

    diag = collect_diagnostics()
    assert diag.dmi.get("sys_vendor") == "TONGFANG"
    assert diag.dmi.get("product_name") == "GM5"
    assert any(e.get("name") == "tongfang::kbd_backlight" for e in diag.leds)
    assert any(e.get("name") == "tongfang::kbd_backlight" for e in diag.sysfs_leds)
    assert any(e.get("name") == "input3::capslock" for e in diag.sysfs_leds)
    assert isinstance(diag.system, dict)
    assert isinstance(diag.hints, dict)
    assert isinstance(diag.app, dict)
    assert isinstance(diag.power_supply, dict)
    assert isinstance(diag.backends, dict)
    assert isinstance(diag.usb_devices, list)
    assert isinstance(diag.config, dict)
    assert isinstance(diag.process, dict)

    # Backend diagnostics should include tier/provider/priority metadata.
    probes = diag.backends.get("probes")
    assert isinstance(probes, list)
    assert any(isinstance(p, dict) and p.get("name") == "sysfs-leds" for p in probes)
    sysfs_probe = next(p for p in probes if isinstance(p, dict) and p.get("name") == "sysfs-leds")
    assert sysfs_probe.get("tier") == 1
    assert sysfs_probe.get("provider") == "kernel-sysfs"
    assert isinstance(sysfs_probe.get("priority"), int)

    # Sysfs candidate snapshot should exist (root is sanitized when overridden).
    sysfs_cand = diag.backends.get("sysfs_led_candidates")
    assert isinstance(sysfs_cand, dict)
    assert "exists" in sysfs_cand

    text = format_diagnostics_text(diag)
    assert "DMI:" in text
    assert "Sysfs LEDs:" in text


def test_format_empty_diagnostics() -> None:
    # If sysfs doesn't exist, collector may return empties. Formatter should be stable.
    diag = collect_diagnostics()
    assert isinstance(format_diagnostics_text(diag), str)


def test_format_support_hints_for_unsupported_usb_device() -> None:
    diag = Diagnostics(
        dmi={},
        leds=[],
        sysfs_leds=[],
        usb_ids=[],
        env={},
        virt={},
        system={},
        hints={},
        app={},
        power_supply={},
        backends={
            "requested": "auto",
            "selected": None,
            "probes": [
                {
                    "name": "ite8291r3",
                    "available": False,
                    "confidence": 0,
                    "reason": "usb device present but unsupported by ite8291r3 backend (0x048d:0xc966)",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0xc966"},
                }
            ],
        },
        usb_devices=[{"idVendor": "0x048d", "idProduct": "0xc966", "product": "Legion keyboard"}],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)
    assert "Support hints:" in text
    assert "0x048d:0xc966" in text
