from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.core.backends.sysfs.common as sysfs_common
import src.core.backends.sysfs_mouse.common as sysfs_mouse_common
import src.core.diagnostics.collectors as diagnostics_collectors
import src.core.diagnostics.collectors.backends as collectors_backends
import src.core.diagnostics.io as diagnostics_io
from src.core.diagnostics import collect_diagnostics, format_diagnostics_text
from src.core.diagnostics.support import ITE8910_SPEED_PROBE_KEY
from src.core.diagnostics.collectors._backends_sysfs import sysfs_led_candidates_snapshot
from src.core.diagnostics.model import Diagnostics, DiagnosticsConfigSnapshot


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
    assert isinstance(diag.config, DiagnosticsConfigSnapshot)
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
    sysfs_mouse_cand = diag.backends.get("sysfs_mouse_candidates")
    assert isinstance(sysfs_mouse_cand, dict)
    assert "exists" in sysfs_mouse_cand

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


def test_sysfs_led_candidates_snapshot_records_scoring_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_sysfs_mouse_candidates_snapshot_records_rejection_reason(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    leds_root = tmp_path / "sys" / "class" / "leds"
    led_dir = leds_root / "steelseries::logo"
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text("1\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text("10\n", encoding="utf-8")
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(leds_root))

    snapshot = diagnostics_collectors._backends_sysfs.sysfs_mouse_candidates_snapshot()

    assert snapshot["candidates_count"] == 1
    assert snapshot["matched_count"] == 0
    assert snapshot["eligible_count"] == 0
    assert snapshot["top"][0]["name"] == "steelseries::logo"
    assert snapshot["top"][0]["matched"] is False
    assert "no mouse/pointer evidence" in snapshot["top"][0]["reasons"][0]


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


def test_probe_backend_propagates_unexpected_probe_boundary_failures() -> None:
    class BrokenBackend:
        name = "broken-backend"

        def probe(self) -> object:
            raise AssertionError("unexpected probe bug")

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        collectors_backends._probe_backend(BrokenBackend())


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
    monkeypatch.setattr(collectors_backends, "_iter_auxiliary_probe_backends", lambda: [])
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


def test_backend_probe_snapshot_propagates_unexpected_selection_boundary_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.backends.registry as backend_registry

    monkeypatch.setattr(collectors_backends, "_selection_is_blocked_under_pytest", lambda: (False, None))
    monkeypatch.setattr(collectors_backends, "build_backend_speed_probe_plans", lambda backends_snapshot: [])
    monkeypatch.setattr(collectors_backends, "_iter_auxiliary_probe_backends", lambda: [])
    monkeypatch.setattr(collectors_backends, "sysfs_led_candidates_snapshot", lambda: {})
    monkeypatch.setattr(backend_registry, "iter_backends", lambda: [])
    monkeypatch.setattr(
        backend_registry,
        "select_backend",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected selection bug")),
    )

    with pytest.raises(AssertionError, match="unexpected selection bug"):
        collectors_backends.backend_probe_snapshot()


def test_iter_auxiliary_probe_backends_propagates_unexpected_registration_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.endswith("sysfs_mouse.backend"):
            raise AssertionError("unexpected auxiliary import bug")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(AssertionError, match="unexpected auxiliary import bug"):
        collectors_backends._iter_auxiliary_probe_backends()


def test_read_text_returns_none_on_decode_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.txt"
    path.write_bytes(b"x")

    def bad_read_text(self: Path, *, encoding: str) -> str:
        assert self == path
        assert encoding == "utf-8"
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "boom")

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    assert diagnostics_io.read_text(path) is None


def test_run_command_returns_none_on_subprocess_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics_io.shutil, "which", lambda exe: f"/usr/bin/{exe}")

    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["echo", "hi"], timeout=1.5)

    monkeypatch.setattr(diagnostics_io.subprocess, "run", boom)

    assert diagnostics_io.run_command(["echo", "hi"]) is None


def test_read_kv_file_returns_empty_dict_on_read_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "os-release"
    path.write_text("ID=fedora\n", encoding="utf-8")

    def bad_read_text(self: Path, *, encoding: str, errors: str) -> str:
        assert self == path
        assert encoding == "utf-8"
        assert errors == "ignore"
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    assert diagnostics_io.read_kv_file(path) == {}


@pytest.mark.parametrize("value", [None, object(), "0xzz"])
def test_parse_hex_int_returns_none_for_invalid_values(value: object) -> None:
    assert diagnostics_io.parse_hex_int(value) is None


def test_config_snapshot_ignores_stat_metadata_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"effect": "wave", "brightness": 25}', encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_stat = Path.stat

    def bad_stat(self: Path, *args: object, **kwargs: object):
        if self == cfg_path:
            raise PermissionError("denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", bad_stat)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.mtime is None
    assert dict(snapshot.settings) == {"effect": "wave", "brightness": 25}
    assert snapshot.to_dict() == {"present": True, "settings": {"effect": "wave", "brightness": 25}}


def test_config_snapshot_reports_invalid_json_without_crashing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"effect": ', encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error is not None and snapshot.error.startswith("invalid JSON at line 1 column ")
    assert snapshot.error is not None and str(cfg_path) not in snapshot.error


def test_config_snapshot_sanitizes_unreadable_config_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "nested" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise PermissionError(13, "Permission denied", str(cfg_path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error == "Permission denied"
    assert snapshot.error is not None and str(cfg_path) not in snapshot.error


def test_config_snapshot_logs_unexpected_boundary_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise RuntimeError(f"unexpected failure while reading {cfg_path}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    with caplog.at_level(logging.DEBUG, logger=diagnostics_collectors.__name__):
        snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error == "unexpected failure while reading config.json"
    records = [
        record
        for record in caplog.records
        if "Failed to collect config snapshot during diagnostics collection" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_config_snapshot_propagates_unexpected_boundary_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise AssertionError("unexpected config snapshot bug")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    with pytest.raises(AssertionError, match="unexpected config snapshot bug"):
        diagnostics_collectors.config_snapshot()
