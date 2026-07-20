from __future__ import annotations

import json
import logging

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.gui.windows.support as support_window
from tests.gui.windows._support_window_test_fakes import make_window as _make_window


def test_copy_debug_output_requires_existing_json() -> None:
    window = _make_window()

    window.copy_debug_output()

    assert window.root.clipboard_values == []
    assert window.status_label.options["text"] == "Run diagnostics first"


def test_save_debug_output_writes_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    window = _make_window(diagnostics_json='{"ok": true}')
    out_path = tmp_path / "diag.json"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))

    window.save_debug_output()

    assert out_path.read_text(encoding="utf-8") == '{"ok": true}'
    assert window.status_label.options["text"] == "Saved output"


def test_save_support_bundle_writes_combined_json(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    window = _make_window(diagnostics_json='{"diag": 1}', discovery_json='{"disc": 2}')
    out_path = tmp_path / "bundle.json"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))
    monkeypatch.setattr(
        support_window,
        "build_support_bundle_payload",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "diagnostics": diagnostics,
            "device_discovery": discovery,
            "supplemental_evidence": supplemental_evidence,
            "issue_report": {"template": "hardware-support"},
        },
    )
    window._supplemental_evidence = {"captures": {"lsusb_verbose": {"ok": True}}}

    window.save_support_bundle()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == {
        "diagnostics": {"diag": 1},
        "device_discovery": {"disc": 2},
        "supplemental_evidence": {"captures": {"lsusb_verbose": {"ok": True}}},
        "issue_report": {"template": "hardware-support"},
    }
    assert window.status_label.options["text"] == "Saved support bundle"


def test_save_support_bundle_autocollects_missing_discovery_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    window = _make_window(diagnostics_json='{"diag": 1}')
    out_path = tmp_path / "bundle.json"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))
    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {"selected_backend": "ite8258_perkey_chassis", "include_usb": include_usb},
    )
    monkeypatch.setattr(
        support_window,
        "build_support_bundle_payload",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "diagnostics": diagnostics,
            "device_discovery": discovery,
            "supplemental_evidence": supplemental_evidence,
            "issue_report": {"template": "experimental-backend-confirmation"},
        },
    )

    window.save_support_bundle()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["diagnostics"] == {"diag": 1}
    assert payload["device_discovery"] == {"selected_backend": "ite8258_perkey_chassis", "include_usb": True}
    assert json.loads(window._discovery_json)["selected_backend"] == "ite8258_perkey_chassis"
    assert window.status_label.options["text"] == "Saved support bundle"


def test_save_support_bundle_logs_unexpected_builder_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    window = _make_window(diagnostics_json='{"diag": 1}')
    out_path = tmp_path / "bundle.json"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))

    def _raise_unexpected(**kwargs) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(support_window, "build_support_bundle_payload", _raise_unexpected)

    with caplog.at_level(logging.ERROR, logger=support_window.logger.name):
        window.save_support_bundle()

    assert window.status_label.options["text"] == "Failed to save bundle"
    assert "Failed to save support bundle" in caplog.text


def test_save_support_bundle_propagates_unexpected_builder_failures(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    window = _make_window(diagnostics_json='{"diag": 1}')
    out_path = tmp_path / "bundle.json"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))

    def _raise_unexpected(**kwargs) -> dict[str, object]:
        raise AssertionError("unexpected bundle bug")

    monkeypatch.setattr(support_window, "build_support_bundle_payload", _raise_unexpected)

    with pytest.raises(AssertionError, match="unexpected bundle bug"):
        window.save_support_bundle()


def test_open_issue_form_copies_url_when_browser_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    window._issue_report = {"issue_url": "https://example.invalid/form"}
    monkeypatch.setattr(
        support_window.webbrowser, "open", lambda url, new=0: (_ for _ in ()).throw(OSError("no browser"))
    )

    window.open_issue_form()

    assert window.root.clipboard_values == ["https://example.invalid/form"]
    assert window.status_label.options["text"] == "Couldn't open browser; issue URL copied"


def test_copy_issue_report_requires_existing_draft() -> None:
    window = _make_window()

    window.copy_issue_report()

    assert window.root.clipboard_values == []
    assert window.status_label.options["text"] == "Run diagnostics or discovery first"


def test_refresh_issue_report_updates_preview_and_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(diagnostics_json='{"app": {"version": "0.19.1"}}')
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "template_label": "Hardware support / diagnostics",
            "issue_url": "https://example.invalid/hardware",
            "markdown": "Template: Hardware support / diagnostics\n",
        },
    )

    window._refresh_issue_report()

    assert window.issue_meta_label.options["text"] == (
        "Suggested template: Hardware support / diagnostics\nIssue URL: https://example.invalid/hardware"
    )
    assert window.txt_issue.contents == "Template: Hardware support / diagnostics\n"


def test_refresh_issue_report_resets_preview_when_inputs_missing() -> None:
    window = _make_window()
    window._issue_report = {"markdown": "stale"}

    window._refresh_issue_report()

    assert window._issue_report is None
    assert window.issue_meta_label.options["text"] == "Suggested template: run diagnostics or discovery first"
    assert "Run diagnostics or discovery" in window.txt_issue.contents


def test_copy_debug_output_handles_clipboard_runtime_errors() -> None:
    window = _make_window(diagnostics_json='{"ok": true}')

    def _fail_clipboard(_value: str) -> None:
        raise RuntimeError("clipboard unavailable")

    window.root.clipboard_append = _fail_clipboard

    window.copy_debug_output()

    assert window.status_label.options["text"] == "Clipboard copy failed"


def test_save_issue_report_writes_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    window = _make_window()
    window._issue_report = {"markdown": "# issue draft\n"}
    out_path = tmp_path / "issue.md"
    monkeypatch.setattr(support_window.filedialog, "asksaveasfilename", lambda **kwargs: str(out_path))

    window.save_issue_report()

    assert out_path.read_text(encoding="utf-8") == "# issue draft\n"
    assert window.status_label.options["text"] == "Saved output"


def test_save_support_bundle_builds_job_inputs_without_changing_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setattr(support_window.support_jobs, "save_support_bundle", _capture)

    window.save_support_bundle()

    assert seen["window"] is window
    assert seen["asksaveasfilename"] is support_window.filedialog.asksaveasfilename
    assert seen["build_support_bundle_payload"] is support_window.build_support_bundle_payload
    assert seen["logger"] is support_window.logger
    assert seen["collect_diagnostics_text"] is support_window.collect_diagnostics_text
    assert seen["collect_device_discovery"] is support_window.collect_device_discovery


def test_open_issue_form_builds_job_inputs_without_changing_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setattr(support_window.support_jobs, "open_issue_form", _capture)

    window.open_issue_form()

    assert seen["window"] is window
    assert seen["issue_url"] == support_window.ISSUE_URL
    assert seen["open_browser"] is support_window.webbrowser.open
    assert seen["browser_open_errors"] == support_window._BROWSER_OPEN_ERRORS
    assert seen["tk_runtime_errors"] == support_window._TK_RUNTIME_ERRORS
