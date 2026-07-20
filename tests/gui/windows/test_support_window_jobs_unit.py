from __future__ import annotations

import json

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.gui.windows.support as support_window
from tests.gui.windows._support_window_test_fakes import make_window as _make_window


def test_run_discovery_updates_text_and_enables_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {
            "selected_backend": "ite8291r3_perkey",
            "summary": {"candidate_count": 1, "supported_count": 0, "attention_count": 1},
            "usb_ids": [],
            "candidates": [],
            "support_actions": {
                "recommended_issue_template": "hardware-support",
                "recommended_issue_url": "https://example.invalid/hardware",
            },
        },
    )
    monkeypatch.setattr(support_window, "format_device_discovery_text", lambda payload: "formatted discovery")
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid/hardware",
        },
    )
    monkeypatch.setattr(
        support_window, "build_additional_evidence_plan", lambda discovery: {"automated": [], "usb_id": ""}
    )
    monkeypatch.setattr(support_window.messagebox, "askyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.run_discovery()

    assert json.loads(window._discovery_json)["selected_backend"] == "ite8291r3_perkey"
    assert window.txt_discovery.contents == "formatted discovery"
    assert window.btn_run_discovery.options["state"] == "normal"
    assert window.btn_copy_discovery.options["state"] == "normal"
    assert window.btn_copy_issue.options["state"] == "normal"
    assert window.txt_issue.contents == "issue draft"


def test_run_debug_returns_fallback_text_for_expected_collection_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    logged: list[str] = []

    monkeypatch.setattr(
        support_window,
        "collect_diagnostics_text",
        lambda *, include_usb: (_ for _ in ()).throw(RuntimeError("busy")),
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.logger, "exception", lambda message: logged.append(message))

    window.run_debug()

    assert window._diagnostics_json == ""
    assert window.txt_debug.contents == "Failed to collect diagnostics: busy"
    assert window.btn_run_debug.options["state"] == "normal"
    assert logged == ["Failed to collect diagnostics"]


def test_run_debug_propagates_unexpected_collection_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()

    monkeypatch.setattr(
        support_window,
        "collect_diagnostics_text",
        lambda *, include_usb: (_ for _ in ()).throw(AssertionError("unexpected diagnostics bug")),
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    with pytest.raises(AssertionError, match="unexpected diagnostics bug"):
        window.run_debug()


def test_run_debug_builds_job_inputs_without_changing_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setattr(support_window.support_jobs, "run_debug", _capture)

    window.run_debug()

    assert seen["window"] is window
    assert seen["collect_diagnostics_text"] is support_window.collect_diagnostics_text
    assert seen["run_in_thread"] is support_window.run_in_thread
    assert seen["logger"] is support_window.logger


def test_run_discovery_returns_fallback_text_for_expected_collection_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    logged: list[str] = []

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: (_ for _ in ()).throw(RuntimeError("probe busy")),
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.logger, "exception", lambda message: logged.append(message))

    window.run_discovery()

    assert window._discovery_json == ""
    assert window.txt_discovery.contents == "Failed to scan devices: probe busy"
    assert window.btn_run_discovery.options["state"] == "normal"
    assert logged == ["Failed to collect discovery snapshot"]


def test_run_discovery_propagates_unexpected_collection_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: (_ for _ in ()).throw(AssertionError("unexpected discovery bug")),
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    with pytest.raises(AssertionError, match="unexpected discovery bug"):
        window.run_discovery()


def test_run_discovery_builds_job_inputs_without_changing_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setattr(support_window.support_jobs, "run_discovery", _capture)

    window.run_discovery()

    assert seen["window"] is window
    assert seen["collect_device_discovery"] is support_window.collect_device_discovery
    assert seen["format_device_discovery_text"] is support_window.format_device_discovery_text
    assert seen["run_in_thread"] is support_window.run_in_thread
    assert seen["logger"] is support_window.logger


def test_collect_missing_evidence_updates_bundle_state(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        discovery_json='{"candidates": [{"usb_vid": "0x048d", "usb_pid": "0x7001", "status": "known_dormant"}]}'
    )

    monkeypatch.setattr(
        support_window,
        "build_additional_evidence_plan",
        lambda discovery: {"usb_id": "048d:7001", "automated": [{"key": "lsusb_verbose", "requires_root": False}]},
    )
    monkeypatch.setattr(
        support_window,
        "collect_additional_evidence",
        lambda discovery, *, allow_privileged: {"captures": {"lsusb_verbose": {"ok": True, "stdout": "dump"}}},
    )
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.collect_missing_evidence(prompt=False)

    assert window._supplemental_evidence == {"captures": {"lsusb_verbose": {"ok": True, "stdout": "dump"}}}
    assert window.status_label.options["text"] == "Additional evidence collected"


def test_collect_missing_evidence_builds_job_inputs_without_changing_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setattr(support_window.support_jobs, "collect_missing_evidence", _capture)

    window.collect_missing_evidence(prompt=False)

    assert seen["window"] is window
    assert seen["prompt"] is False
    assert callable(seen["current_capture_plan_fn"])
    assert seen["messagebox"] is support_window.messagebox
    assert seen["tk_runtime_errors"] == support_window._TK_RUNTIME_ERRORS
    assert seen["collect_additional_evidence"] is support_window.collect_additional_evidence
    assert seen["run_in_thread"] is support_window.run_in_thread


def test_run_discovery_preserves_recorded_backend_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    window._supplemental_evidence = {
        "backend_probes": {
            "ite8910_speed": {
                "backend": "ite8910_perkey",
                "effect_name": "spectrum_cycle",
            }
        },
        "captures": {"lsusb_verbose": {"ok": True}},
    }

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {"selected_backend": "ite8910_perkey", "summary": {"candidate_count": 1}},
    )
    monkeypatch.setattr(support_window, "format_device_discovery_text", lambda payload: "formatted discovery")
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(
        support_window, "build_additional_evidence_plan", lambda discovery: {"automated": [], "usb_id": ""}
    )
    monkeypatch.setattr(support_window.messagebox, "askyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.run_discovery()

    assert window._supplemental_evidence == {
        "backend_probes": {
            "ite8910_speed": {
                "backend": "ite8910_perkey",
                "effect_name": "spectrum_cycle",
            }
        }
    }
