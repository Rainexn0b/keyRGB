from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src.core.backends.sysfs.common as sysfs_common
import src.core.diagnostics.collectors_backends as collectors_backends
from src.core.diagnostics import collect_diagnostics, format_diagnostics_text
from src.core.diagnostics.backend_speed_probe import ITE8910_SPEED_PROBE_KEY
from src.core.diagnostics._collectors_backends_sysfs import sysfs_led_candidates_snapshot
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

    guided_speed_probes = diag.backends.get("guided_speed_probes")
    assert isinstance(guided_speed_probes, list)

    # Sysfs candidate snapshot should exist (root is sanitized when overridden).
    sysfs_cand = diag.backends.get("sysfs_led_candidates")
    assert isinstance(sysfs_cand, dict)
    assert "exists" in sysfs_cand

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
            "selected": "ite8910",
            "requested": "auto",
            "probes": [],
            "guided_speed_probes": [
                {
                    "key": ITE8910_SPEED_PROBE_KEY,
                    "backend": "ite8910",
                    "effect_name": "spectrum_cycle",
                    "requested_ui_speeds": [1, 3, 5, 7, 10],
                    "samples": [
                        {"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"},
                        {"ui_speed": 10, "payload_speed": 10, "raw_speed_hex": "0x0a"},
                    ],
                    "expectation": "Higher UI speed values should look faster on ite8910.",
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
    assert "Higher UI speed values should look faster on ite8910." in text


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
                    "name": "ite8291r3",
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


def test_sysfs_led_candidates_snapshot_records_root_resolution_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Path:
        raise RuntimeError("root failed")

    monkeypatch.setattr(sysfs_common, "_leds_root", boom)

    snapshot = sysfs_led_candidates_snapshot()

    assert "errors" in snapshot
    assert snapshot["errors"][0]["stage"] == "resolve_leds_root"
    assert snapshot["errors"][0]["type"] == "RuntimeError"
    assert "RuntimeError: root failed" in snapshot["errors"][0]["traceback"]


def test_sysfs_led_candidates_snapshot_records_scoring_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    leds_root = tmp_path / "sys" / "class" / "leds"
    led_dir = leds_root / "tongfang::kbd_backlight"
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text("1\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(leds_root))

    def bad_score(path: Path) -> int:
        raise RuntimeError(f"cannot score {path.name}")

    monkeypatch.setattr(sysfs_common, "_score_led_dir", bad_score)

    snapshot = sysfs_led_candidates_snapshot()

    assert snapshot["candidates_count"] == 1
    assert snapshot["top"][0]["name"] == "tongfang::kbd_backlight"
    assert snapshot["top"][0]["score"] == 0
    assert any(error.get("stage") == "score_led_dir" for error in snapshot.get("errors", []))
    assert any(
        "RuntimeError: cannot score tongfang::kbd_backlight" in str(error.get("traceback") or "")
        for error in snapshot.get("errors", [])
    )



def test_probe_backend_logs_probe_boundary_failures(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenBackend:
        name = "broken-backend"
        priority = 7

        def probe(self) -> object:
            raise RuntimeError("probe failed")

    with caplog.at_level(logging.DEBUG, logger=collectors_backends.__name__):
        entry = collectors_backends._probe_backend(BrokenBackend())

    assert entry["name"] == "broken-backend"
    assert entry["available"] is False
    assert entry["confidence"] == 0
    assert entry["reason"] == "probe exception: probe failed"

    records = [
        record
        for record in caplog.records
        if "Failed to probe backend during diagnostics collection" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_probe_backend_tolerates_runtime_metadata_getter_failures() -> None:
    class BrokenMetadataBackend:
        name = "broken-meta"

        def is_available(self) -> bool:
            return True

        
        @property
        def priority(self) -> int:
            raise RuntimeError("priority failed")

        
        @property
        def stability(self) -> object:
            raise RuntimeError("stability failed")

        
        @property
        def experimental_evidence(self) -> object:
            raise RuntimeError("evidence failed")

    entry = collectors_backends._probe_backend(BrokenMetadataBackend())

    assert entry["available"] is True
    assert entry["priority"] == 0
    assert "stability" not in entry
    assert "experimental_evidence" not in entry
    assert "selection_enabled" not in entry


def test_backend_probe_snapshot_logs_selection_boundary_failures(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import src.core.backends.registry as backend_registry

    monkeypatch.setattr(collectors_backends, "_selection_is_blocked_under_pytest", lambda: (False, None))
    monkeypatch.setattr(collectors_backends, "build_backend_speed_probe_plans", lambda backends_snapshot: [])
    monkeypatch.setattr(collectors_backends, "sysfs_led_candidates_snapshot", lambda: {})
    monkeypatch.setattr(backend_registry, "iter_backends", lambda: [])
    monkeypatch.setattr(
        backend_registry,
        "select_backend",
        lambda: (_ for _ in ()).throw(RuntimeError("selection failed")),
    )

    with caplog.at_level(logging.DEBUG, logger=collectors_backends.__name__):
        snapshot = collectors_backends.backend_probe_snapshot()

    assert snapshot["selected"] is None
    assert snapshot["probes"] == []

    records = [
        record
        for record in caplog.records
        if "Failed to resolve selected backend during diagnostics collection" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None
