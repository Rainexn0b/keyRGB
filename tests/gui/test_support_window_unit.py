from __future__ import annotations

import json
import logging
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src.gui.windows.support as support_window


class _FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.options = dict(kwargs)
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def focus_set(self) -> None:
        self.options["focused"] = True


class _FakeText(_FakeWidget):
    def __init__(self, text: str = "") -> None:
        super().__init__(state="disabled")
        self.contents = text

    def delete(self, start: str, end: str) -> None:
        self.contents = ""

    def insert(self, index: str, value: str) -> None:
        self.contents = value


class _FakeRoot:
    def __init__(self) -> None:
        self.clipboard_cleared = 0
        self.clipboard_values: list[str] = []
        self.after_calls: list[tuple[int, object]] = []
        self.title_text = ""
        self.geometry_value = ""
        self.minsize_value: tuple[int, int] | None = None
        self.resizable_value: tuple[bool, bool] | None = None

    def clipboard_clear(self) -> None:
        self.clipboard_cleared += 1

    def clipboard_append(self, value: str) -> None:
        self.clipboard_values.append(value)

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def title(self, value: str) -> None:
        self.title_text = value

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def minsize(self, width: int, height: int) -> None:
        self.minsize_value = (width, height)

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_value = (width, height)

    def mainloop(self) -> None:
        return


def _flush_after(root: _FakeRoot) -> None:
    callbacks = list(root.after_calls)
    for _delay_ms, callback in callbacks:
        callback()


def _make_window(*, diagnostics_json: str = "", discovery_json: str = ""):
    window = support_window.SupportToolsGUI.__new__(support_window.SupportToolsGUI)
    window.root = _FakeRoot()
    window.status_label = _FakeWidget(text="")
    window.issue_meta_label = _FakeWidget(text="")
    window.txt_debug = _FakeText("stale debug")
    window.txt_discovery = _FakeText("stale discovery")
    window.txt_issue = _FakeText("stale issue")
    window.btn_copy_debug = _FakeWidget(state="disabled")
    window.btn_copy_discovery = _FakeWidget(state="disabled")
    window.btn_save_debug = _FakeWidget(state="disabled")
    window.btn_save_discovery = _FakeWidget(state="disabled")
    window.btn_copy_issue = _FakeWidget(state="disabled")
    window.btn_save_issue = _FakeWidget(state="disabled")
    window.btn_collect_evidence = _FakeWidget(state="disabled")
    window.btn_run_speed_probe = _FakeWidget(state="disabled")
    window.btn_open_issue = _FakeWidget(state="disabled")
    window.btn_save_bundle = _FakeWidget(state="disabled")
    window.btn_run_debug = _FakeWidget(state="normal")
    window.btn_run_discovery = _FakeWidget(state="normal")
    window._diagnostics_json = diagnostics_json
    window._discovery_json = discovery_json
    window._supplemental_evidence = None
    window._issue_report = None
    window._capture_prompt_key = ""
    window._backend_probe_prompt_key = ""
    return window


def test_init_builds_all_sections_before_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    created_roots: list[_FakeRoot] = []

    class _ConstructWidget(_FakeWidget):
        def pack(self, *args, **kwargs) -> None:
            return

    class _ConstructText(_FakeText):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__("")
            self.options.update(kwargs)

        def pack(self, *args, **kwargs) -> None:
            return

    def _make_root() -> _FakeRoot:
        root = _FakeRoot()
        created_roots.append(root)
        return root

    monkeypatch.setattr(support_window.tk, "Tk", _make_root)
    monkeypatch.setattr(support_window.ttk, "Frame", lambda *args, **kwargs: _ConstructWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "Label", lambda *args, **kwargs: _ConstructWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "LabelFrame", lambda *args, **kwargs: _ConstructWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "Button", lambda *args, **kwargs: _ConstructWidget(**kwargs))
    monkeypatch.setattr(support_window.scrolledtext, "ScrolledText", lambda *args, **kwargs: _ConstructText(*args, **kwargs))
    monkeypatch.setattr(support_window, "apply_keyrgb_window_icon", lambda root: None)
    monkeypatch.setattr(support_window, "apply_clam_theme", lambda root, **kwargs: ("#111111", "#eeeeee"))
    monkeypatch.setattr(support_window, "center_window_on_screen", lambda root: None)

    window = support_window.SupportToolsGUI()

    assert created_roots
    assert window.btn_copy_debug.options["state"] == "disabled"
    assert window.btn_copy_discovery.options["state"] == "disabled"
    assert window.btn_copy_issue.options["state"] == "disabled"
    assert window.root.title_text == "KeyRGB - Support Tools"


def test_sync_button_state_tracks_copy_and_save_actions() -> None:
    window = _make_window(diagnostics_json='{"backends": {"guided_speed_probes": [{"backend": "ite8910"}]}}', discovery_json='{"candidate": 1}')
    window._issue_report = {"markdown": "issue draft"}

    window._sync_button_state()

    assert window.btn_copy_debug.options["state"] == "normal"
    assert window.btn_copy_discovery.options["state"] == "normal"
    assert window.btn_save_debug.options["state"] == "normal"
    assert window.btn_save_discovery.options["state"] == "normal"
    assert window.btn_copy_issue.options["state"] == "normal"
    assert window.btn_save_issue.options["state"] == "normal"
    assert window.btn_collect_evidence.options["state"] == "disabled"
    assert window.btn_run_speed_probe.options["state"] == "normal"
    assert window.btn_open_issue.options["state"] == "normal"
    assert window.btn_save_bundle.options["state"] == "normal"


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


def test_open_issue_form_copies_url_when_browser_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    window._issue_report = {"issue_url": "https://example.invalid/form"}
    monkeypatch.setattr(support_window.webbrowser, "open", lambda url, new=0: (_ for _ in ()).throw(OSError("no browser")))

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
        "Suggested template: Hardware support / diagnostics\n"
        "Issue URL: https://example.invalid/hardware"
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


def test_run_discovery_updates_text_and_enables_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {"selected_backend": "ite8291r3", "summary": {"candidate_count": 1, "supported_count": 0, "attention_count": 1}, "usb_ids": [], "candidates": [], "support_actions": {"recommended_issue_template": "hardware-support", "recommended_issue_url": "https://example.invalid/hardware"}},
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
    monkeypatch.setattr(support_window, "build_additional_evidence_plan", lambda discovery: {"automated": [], "usb_id": ""})
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.run_discovery()

    assert json.loads(window._discovery_json)["selected_backend"] == "ite8291r3"
    assert window.txt_discovery.contents == "formatted discovery"
    assert window.btn_run_discovery.options["state"] == "normal"
    assert window.btn_copy_discovery.options["state"] == "normal"
    assert window.btn_copy_issue.options["state"] == "normal"
    assert window.txt_issue.contents == "issue draft"


def test_collect_missing_evidence_updates_bundle_state(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(discovery_json='{"candidates": [{"usb_vid": "0x048d", "usb_pid": "0x7001", "status": "known_dormant"}]}')

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
        lambda *, diagnostics, discovery, supplemental_evidence=None: {"markdown": "issue draft", "issue_url": "https://example.invalid"},
    )
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.collect_missing_evidence(prompt=False)

    assert window._supplemental_evidence == {"captures": {"lsusb_verbose": {"ok": True, "stdout": "dump"}}}
    assert window.status_label.options["text"] == "Additional evidence collected"


def test_run_backend_speed_probe_records_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8910_speed", "backend": "ite8910", "effect_name": "spectrum_cycle", "requested_ui_speeds": [1, 3], "samples": [{"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"}] , "instructions": ["Do the thing"], "observation_prompt": "Notes?"}]}}')
    monkeypatch.setattr(support_window.messagebox, "showinfo", lambda *args, **kwargs: True)
    monkeypatch.setattr(support_window.messagebox, "askyesnocancel", lambda *args, **kwargs: False)
    monkeypatch.setattr(support_window.simpledialog, "askstring", lambda *args, **kwargs: "1 and 3 looked too close")
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {"markdown": "issue draft", "issue_url": "https://example.invalid"},
    )

    window.run_backend_speed_probe(prompt=False)

    assert window._supplemental_evidence is not None
    backend_probes = window._supplemental_evidence.get("backend_probes")
    assert isinstance(backend_probes, dict)
    probe = backend_probes["ite8910_speed"]
    assert probe["backend"] == "ite8910"
    assert probe["observation"]["distinct_steps"] is False
    assert probe["observation"]["notes"] == "1 and 3 looked too close"
    assert window.status_label.options["text"] == "Backend speed probe recorded"


def test_run_discovery_preserves_recorded_backend_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()
    window._supplemental_evidence = {
        "backend_probes": {
            "ite8910_speed": {
                "backend": "ite8910",
                "effect_name": "spectrum_cycle",
            }
        },
        "captures": {"lsusb_verbose": {"ok": True}},
    }

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {"selected_backend": "ite8910", "summary": {"candidate_count": 1}},
    )
    monkeypatch.setattr(support_window, "format_device_discovery_text", lambda payload: "formatted discovery")
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {"markdown": "issue draft", "issue_url": "https://example.invalid"},
    )
    monkeypatch.setattr(support_window, "build_additional_evidence_plan", lambda discovery: {"automated": [], "usb_id": ""})
    monkeypatch.setattr(support_window.messagebox, "askyesno", lambda *args, **kwargs: False)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))

    window.run_discovery()

    assert window._supplemental_evidence == {
        "backend_probes": {
            "ite8910_speed": {
                "backend": "ite8910",
                "effect_name": "spectrum_cycle",
            }
        }
    }


def test_set_status_clears_message_after_delay() -> None:
    window = _make_window()

    window._set_status("Ready", ok=True)

    assert window.status_label.options["text"] == "Ready"
    _flush_after(window.root)
    assert window.status_label.options["text"] == ""