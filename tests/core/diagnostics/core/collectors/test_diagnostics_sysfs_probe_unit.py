from __future__ import annotations

import logging
from pathlib import Path

import pytest

import keyrgb.core.backends.sysfs.common as sysfs_common
import keyrgb.core.diagnostics.collectors.backends as collectors_backends
from keyrgb.core.diagnostics.collectors.sysfs_backends import (
    sysfs_led_candidates_snapshot,
    sysfs_mouse_candidates_snapshot,
)


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


def test_sysfs_mouse_candidates_snapshot_records_rejection_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    leds_root = tmp_path / "sys" / "class" / "leds"
    led_dir = leds_root / "steelseries::logo"
    led_dir.mkdir(parents=True)
    (led_dir / "brightness").write_text("1\n", encoding="utf-8")
    (led_dir / "max_brightness").write_text("10\n", encoding="utf-8")
    (led_dir / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(leds_root))

    snapshot = sysfs_mouse_candidates_snapshot()

    assert snapshot["candidates_count"] == 1
    assert snapshot["matched_count"] == 0
    assert snapshot["eligible_count"] == 0
    assert snapshot["top"][0]["name"] == "steelseries::logo"
    assert snapshot["top"][0]["matched"] is False
    assert "no mouse/pointer evidence" in snapshot["top"][0]["reasons"][0]


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
    import keyrgb.core.backends.registry as backend_registry

    monkeypatch.setattr(collectors_backends, "_selection_is_blocked_under_pytest", lambda: (False, None))
    monkeypatch.setattr(collectors_backends, "build_backend_speed_probe_plans", lambda backends_snapshot: [])
    monkeypatch.setattr(collectors_backends, "_iter_auxiliary_probe_backends", list)
    monkeypatch.setattr(collectors_backends, "sysfs_led_candidates_snapshot", dict)
    monkeypatch.setattr(backend_registry, "iter_backends", list)
    monkeypatch.setattr(
        backend_registry,
        "build_backend_selection_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("selection failed")),
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


def test_backend_probe_snapshot_uses_registry_candidate_order_without_reprobing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import keyrgb.core.backends.registry as backend_registry
    from keyrgb.core.backends.base import ProbeResult

    probe_calls: list[str] = []

    class Backend:
        stability = "validated"

        def __init__(self, name: str, priority: int, confidence: int) -> None:
            self.name = name
            self.priority = priority
            self._confidence = confidence

        def probe(self) -> ProbeResult:
            probe_calls.append(self.name)
            return ProbeResult(available=True, reason="test", confidence=self._confidence)

    usb = Backend("ite8291r3_perkey", 100, 95)
    sysfs = Backend("sysfs-leds", 10, 60)
    monkeypatch.setattr(collectors_backends, "_selection_is_blocked_under_pytest", lambda: (False, None))
    monkeypatch.setattr(collectors_backends, "build_backend_speed_probe_plans", lambda backends_snapshot: [])
    monkeypatch.setattr(collectors_backends, "_iter_auxiliary_probe_backends", list)
    monkeypatch.setattr(collectors_backends, "sysfs_led_candidates_snapshot", dict)
    monkeypatch.setattr(collectors_backends, "sysfs_mouse_candidates_snapshot", dict)
    monkeypatch.setattr(backend_registry, "iter_backends", lambda: [usb, sysfs])

    snapshot = collectors_backends.backend_probe_snapshot()

    assert snapshot["selected"] == "sysfs-leds"
    assert [candidate["name"] for candidate in snapshot["candidates_sorted"]] == [
        "sysfs-leds",
        "ite8291r3_perkey",
    ]
    assert snapshot["selection"]["policy"] == "kernel/sysfs safety tier, then confidence, then priority"
    assert probe_calls == ["ite8291r3_perkey", "sysfs-leds"]


def test_backend_probe_snapshot_propagates_unexpected_selection_boundary_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import keyrgb.core.backends.registry as backend_registry

    monkeypatch.setattr(collectors_backends, "_selection_is_blocked_under_pytest", lambda: (False, None))
    monkeypatch.setattr(collectors_backends, "build_backend_speed_probe_plans", lambda backends_snapshot: [])
    monkeypatch.setattr(collectors_backends, "_iter_auxiliary_probe_backends", list)
    monkeypatch.setattr(collectors_backends, "sysfs_led_candidates_snapshot", dict)
    monkeypatch.setattr(backend_registry, "iter_backends", list)
    monkeypatch.setattr(
        backend_registry,
        "build_backend_selection_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected selection bug")),
    )

    with pytest.raises(AssertionError, match="unexpected selection bug"):
        collectors_backends.backend_probe_snapshot()


def test_iter_auxiliary_probe_backends_propagates_unexpected_registration_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.backends.registry import BackendSpec

    def boom() -> object:
        raise AssertionError("unexpected auxiliary factory bug")

    monkeypatch.setattr(
        "keyrgb.core.backends.registry.iter_auxiliary_specs",
        lambda: [
            BackendSpec(
                name="sysfs-mouse",
                priority=10,
                factory=boom,
            )
        ],
    )

    with pytest.raises(AssertionError, match="unexpected auxiliary factory bug"):
        collectors_backends._iter_auxiliary_probe_backends()
