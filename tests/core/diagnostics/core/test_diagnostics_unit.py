from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from keyrgb.core.config._settings_view import ConfigSettingsView
from keyrgb.core.diagnostics import collect_diagnostics, format_diagnostics_text
from keyrgb.core.diagnostics.model import Diagnostics, DiagnosticsConfigSnapshot
from keyrgb.core.diagnostics.support import ITE8910_SPEED_PROBE_KEY


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
    assert isinstance(diag.system, Mapping)
    assert isinstance(diag.hints, Mapping)
    assert isinstance(diag.app, Mapping)
    assert isinstance(diag.power_supply, Mapping)
    assert isinstance(diag.backends, Mapping)
    assert isinstance(diag.usb_devices, Sequence) and not isinstance(diag.usb_devices, str)
    assert isinstance(diag.config, DiagnosticsConfigSnapshot)
    assert isinstance(diag.process, Mapping)

    # Backend diagnostics should include tier/provider/priority metadata.
    probes = diag.backends.get("probes")
    assert isinstance(probes, Sequence) and not isinstance(probes, str)
    assert any(isinstance(p, Mapping) and p.get("name") == "sysfs-leds" for p in probes)
    sysfs_probe = next(p for p in probes if isinstance(p, Mapping) and p.get("name") == "sysfs-leds")
    assert sysfs_probe.get("tier") == 1
    assert sysfs_probe.get("provider") == "kernel-sysfs"
    assert isinstance(sysfs_probe.get("priority"), int)

    guided_speed_probes = diag.backends.get("guided_speed_probes")
    assert isinstance(guided_speed_probes, Sequence) and not isinstance(guided_speed_probes, str)

    # Sysfs candidate snapshot should exist (root is sanitized when overridden).
    sysfs_cand = diag.backends.get("sysfs_led_candidates")
    assert isinstance(sysfs_cand, Mapping) or sysfs_cand is None
    assert sysfs_cand is not None and "exists" in sysfs_cand
    sysfs_mouse_cand = diag.backends.get("sysfs_mouse_candidates")
    assert isinstance(sysfs_mouse_cand, Mapping) or sysfs_mouse_cand is None
    assert sysfs_mouse_cand is not None and "exists" in sysfs_mouse_cand

    text = format_diagnostics_text(diag)
    assert "DMI:" in text
    assert "Sysfs LEDs:" in text


def test_format_diagnostics_text_includes_guided_speed_probe_section() -> None:
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
            "selected": "ite8910_perkey",
            "requested": "auto",
            "probes": [],
            "guided_speed_probes": [
                {
                    "key": ITE8910_SPEED_PROBE_KEY,
                    "backend": "ite8910_perkey",
                    "effect_name": "spectrum_cycle",
                    "requested_ui_speeds": [1, 3, 5, 7, 10],
                    "samples": [
                        {"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"},
                        {"ui_speed": 10, "payload_speed": 10, "raw_speed_hex": "0x0a"},
                    ],
                    "expectation": "Higher UI speed values should look faster on ite8910_perkey.",
                }
            ],
        },
        usb_devices=[],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)

    assert "guided_speed_probes:" in text
    assert "sample: ui=1 payload=1 raw=0x01" in text
    assert "Higher UI speed values should look faster on ite8910_perkey." in text


def test_format_diagnostics_text_includes_backend_capabilities_dimensions_and_matrix() -> None:
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
            "selected": "ite8258_perkey_chassis",
            "requested": "auto",
            "probes": [
                {
                    "name": "ite8258_perkey_chassis",
                    "available": True,
                    "stability": "experimental",
                    "experimental_evidence": "reverse_engineered",
                    "confidence": 83,
                    "reason": "hidraw device present (/dev/hidraw3)",
                    "capabilities": {
                        "brightness": True,
                        "per_key": True,
                        "color": True,
                        "hardware_effects": True,
                        "palette": False,
                    },
                    "dimensions": {"rows": 7, "cols": 20},
                    "diagnostics": {
                        "keyboard_matrix": {
                            "matrix_cells": 140,
                            "mapped_leds": 101,
                            "sparse_holes": 39,
                            "row_mapped_counts": [20, 18, 17, 17, 15, 11, 3],
                        }
                    },
                }
            ],
        },
        usb_devices=[],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)

    assert "capabilities: brightness=True per_key=True color=True hardware_effects=True palette=False" in text
    assert "dimensions: rows=7 cols=20" in text
    assert "keyboard_matrix: cells=140 mapped_leds=101 sparse_holes=39" in text


def test_diagnostics_typed_config_snapshot_serializes_without_shape_changes() -> None:
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
        backends={},
        usb_devices=[],
        config=DiagnosticsConfigSnapshot(
            present=True,
            mtime=123,
            settings={"effect": "wave", "brightness": 25},
            per_key_colors_count=4,
            error="Permission denied",
        ),
        process={},
    )

    assert diag.to_dict()["config"] == {
        "present": True,
        "mtime": 123,
        "settings": {"effect": "wave", "brightness": 25},
        "per_key_colors_count": 4,
        "error": "Permission denied",
    }

    text = format_diagnostics_text(diag)
    assert "Config:" in text
    assert "  present: True" in text
    assert "  mtime: 123" in text
    assert "  per_key_colors_count: 4" in text
    assert "Permission denied" not in text


def test_diagnostics_config_snapshot_wraps_settings_in_typed_settings_view() -> None:
    snap = DiagnosticsConfigSnapshot(settings={"brightness": "25", "effect": "wave"})

    assert isinstance(snap.settings, ConfigSettingsView)
    assert isinstance(snap.settings_view(), ConfigSettingsView)
    assert snap.settings.read_int("brightness", 0) == 25
    with pytest.raises(TypeError):
        snap.settings["effect"] = "rainbow"  # type: ignore[index]

    assert snap.to_dict()["settings"] == {"brightness": "25", "effect": "wave"}


def test_diagnostics_mapping_config_is_readonly_and_detached_from_caller() -> None:
    config_mapping = {"backend": "auto"}

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
        backends={},
        usb_devices=[],
        config=config_mapping,
        process={},
    )

    with pytest.raises(TypeError):
        diag.config["backend"] = "ite8291r3_perkey"  # type: ignore[index]

    config_mapping["backend"] = "ite8291r3_perkey"
    assert diag.to_dict()["config"] == {"backend": "auto"}


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
                    "name": "ite8291r3_perkey",
                    "available": False,
                    "confidence": 0,
                    "reason": "usb device present but unsupported by ite8291r3_perkey backend (0x048d:0xc966)",
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


def test_format_support_hints_for_tuxedo_ite829x_path() -> None:
    diag = Diagnostics(
        dmi={},
        leds=[],
        sysfs_leds=[],
        usb_ids=["048d:8910", "048d:8911"],
        env={},
        virt={},
        system={},
        hints={"modules": ["tuxedo_keyboard"]},
        app={},
        power_supply={},
        backends={
            "requested": "auto",
            "selected": None,
            "probes": [
                {
                    "name": "ite8291r3_perkey",
                    "available": False,
                    "confidence": 0,
                    "reason": "no matching usb device",
                },
                {
                    "name": "sysfs-leds",
                    "available": False,
                    "confidence": 0,
                    "reason": "no matching sysfs LED",
                },
            ],
        },
        usb_devices=[],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)
    assert "Support hints:" in text
    assert "048d:8910, 048d:8911" in text
    assert "ite_829x" in text
    assert "rgb:kbd_backlight" in text


def test_format_support_hints_for_tuxedo_platform_without_led_nodes() -> None:
    diag = Diagnostics(
        dmi={},
        leds=[],
        sysfs_leds=[],
        usb_ids=[],
        env={},
        virt={},
        system={},
        hints={"modules": ["tuxedo_keyboard", "clevo_wmi"]},
        app={},
        power_supply={},
        backends={
            "requested": "auto",
            "selected": None,
            "probes": [
                {
                    "name": "sysfs-leds",
                    "available": False,
                    "confidence": 0,
                    "reason": "no matching sysfs LED",
                },
            ],
        },
        usb_devices=[],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)
    assert "Support hints:" in text
    assert "tuxedo_keyboard is loaded" in text
    assert "kernel-driver binding/export problem" in text
    assert "clevo::kbd_backlight" in text


def test_format_diagnostics_text_includes_sysfs_mouse_candidate_reasons() -> None:
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
            "selected": "sysfs-leds",
            "requested": "auto",
            "probes": [],
            "sysfs_mouse_candidates": {
                "root": "<overridden>",
                "exists": True,
                "candidates_count": 1,
                "matched_count": 0,
                "eligible_count": 0,
                "top": [
                    {
                        "name": "steelseries::logo",
                        "matched": False,
                        "eligible": False,
                        "score": 0,
                        "reasons": ["no mouse/pointer evidence in LED name or device metadata"],
                        "metadata": "",
                        "has_brightness": True,
                        "has_max_brightness": True,
                        "color_capable": True,
                        "brightness_readable": True,
                        "brightness_writable": True,
                    }
                ],
            },
        },
        usb_devices=[],
        config={},
        process={},
    )

    text = format_diagnostics_text(diag)

    assert "sysfs_mouse_candidates:" in text
    assert "steelseries::logo matched=False eligible=False score=0" in text
    assert "reasons: no mouse/pointer evidence in LED name or device metadata" in text
