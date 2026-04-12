from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.gui.windows.support as support_window


class _FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.options = dict(kwargs)
        self.configure_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object, object]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def focus_set(self) -> None:
        self.options["focused"] = True

    def pack(self, *args, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, *args, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.options.setdefault("columnconfigure", []).append((index, weight))

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.options.setdefault("rowconfigure", []).append((index, weight))

    def winfo_width(self) -> int:
        return int(self.options.get("width_px", 640))

    def winfo_reqwidth(self) -> int:
        return int(self.options.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.options.get("reqheight_px", 480))


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
        self.update_idletasks_calls = 0
        self.root_x = 100
        self.root_y = 80
        self.root_width = 1240
        self.root_height = 920
        self.screen_width = 1920
        self.screen_height = 1080

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

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenheight(self) -> int:
        return self.screen_height

    def winfo_screenwidth(self) -> int:
        return self.screen_width

    def winfo_rootx(self) -> int:
        return self.root_x

    def winfo_rooty(self) -> int:
        return self.root_y

    def winfo_width(self) -> int:
        return self.root_width

    def winfo_height(self) -> int:
        return self.root_height

    def mainloop(self) -> None:
        return


def _flush_after(root: _FakeRoot) -> None:
    callbacks = list(root.after_calls)
    for _delay_ms, callback in callbacks:
        callback()


def _make_window(*, diagnostics_json: str = "", discovery_json: str = ""):
    window = support_window.SupportToolsGUI.__new__(support_window.SupportToolsGUI)
    window.root = _FakeRoot()
    window._bg_color = "#111111"
    window._fg_color = "#eeeeee"
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


def _build_support_ui_modules() -> tuple[dict[str, list[_FakeWidget]], SimpleNamespace, SimpleNamespace]:
    registry: dict[str, list[_FakeWidget]] = {"frames": [], "labels": [], "buttons": [], "texts": []}

    def _frame(*args, **kwargs):
        widget = _FakeWidget(**kwargs)
        registry["frames"].append(widget)
        return widget

    def _label(*args, **kwargs):
        widget = _FakeWidget(**kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(*args, **kwargs):
        widget = _FakeWidget(**kwargs)
        registry["buttons"].append(widget)
        return widget

    def _text(*args, **kwargs):
        widget = _FakeText("")
        widget.options.update(kwargs)
        registry["texts"].append(widget)
        return widget

    fake_ttk = SimpleNamespace(Frame=_frame, Label=_label, Button=_button)
    fake_scrolledtext = SimpleNamespace(ScrolledText=_text)
    return registry, fake_ttk, fake_scrolledtext


def _build_support_jobs_ttk() -> tuple[dict[str, list[_FakeWidget]], SimpleNamespace]:
    registry: dict[str, list[_FakeWidget]] = {"frames": [], "buttons": []}

    def _frame(*args, **kwargs):
        widget = _FakeWidget(**kwargs)
        registry["frames"].append(widget)
        return widget

    def _button(*args, **kwargs):
        widget = _FakeWidget(**kwargs)
        registry["buttons"].append(widget)
        return widget

    return registry, SimpleNamespace(Frame=_frame, Button=_button)


def test_init_builds_all_sections_before_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    created_roots: list[_FakeRoot] = []

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

    class _FakeStyle:
        def __init__(self, *args, **kwargs) -> None:
            self.configured: list[tuple[str, dict[str, object]]] = []
            self.mapped: list[tuple[str, dict[str, object]]] = []

        def configure(self, name: str, **kwargs) -> None:
            self.configured.append((name, dict(kwargs)))

        def map(self, name: str, **kwargs) -> None:
            self.mapped.append((name, dict(kwargs)))

    monkeypatch.setattr(support_window.tk, "Tk", _make_root)
    monkeypatch.setattr(support_window.ttk, "Frame", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "Label", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "LabelFrame", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "Button", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support_window.ttk, "Style", lambda *args, **kwargs: _FakeStyle(*args, **kwargs))
    monkeypatch.setattr(
        support_window.scrolledtext, "ScrolledText", lambda *args, **kwargs: _ConstructText(*args, **kwargs)
    )
    monkeypatch.setattr(support_window, "apply_keyrgb_window_icon", lambda root: None)
    monkeypatch.setattr(support_window, "apply_clam_theme", lambda root, **kwargs: ("#111111", "#eeeeee"))
    monkeypatch.setattr(support_window, "center_window_on_screen", lambda root: None)

    window = support_window.SupportToolsGUI()

    assert created_roots
    assert window.btn_copy_debug.options["state"] == "disabled"
    assert window.btn_copy_discovery.options["state"] == "disabled"
    assert window.btn_copy_issue.options["state"] == "disabled"
    assert window.root.title_text == "KeyRGB - Support Tools"
    assert window.root.minsize_value == (960, 720)
    assert window.btn_run_debug.options["style"] == "SupportChecks.Diagnostics.TButton"
    assert window.btn_run_speed_probe.options["style"] == "SupportChecks.Probe.TButton"
    assert window.btn_run_discovery.options["style"] == "SupportChecks.Discovery.TButton"
    assert any(delay == 50 for delay, _callback in window.root.after_calls)


def test_apply_geometry_uses_requested_content_size(monkeypatch: pytest.MonkeyPatch) -> None:
    window = support_window.SupportToolsGUI.__new__(support_window.SupportToolsGUI)
    window.root = _FakeRoot()
    window._main_frame = _FakeWidget(reqwidth_px=1480, reqheight_px=910)

    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "1480x958+10+20"

    monkeypatch.setattr(support_window, "compute_centered_window_geometry", _fake_compute)

    window._apply_geometry()

    assert window.root.update_idletasks_calls == 1
    assert seen == {
        "root": window.root,
        "content_height_px": 910,
        "content_width_px": 1480,
        "footer_height_px": 0,
        "chrome_padding_px": 48,
        "default_w": 1240,
        "default_h": 920,
        "screen_ratio_cap": 0.95,
    }
    assert window.root.geometry_value == "1480x958+10+20"


def test_probe_dialog_dimensions_clamp_to_screen_ratio() -> None:
    window = _make_window()
    window.root.screen_width = 800
    window.root.screen_height = 600

    width, height = support_window.support_jobs._probe_dialog_dimensions(window, width=1200, height=900)

    assert (width, height) == (736, 552)


def test_probe_dialog_geometry_clamps_position_to_visible_screen() -> None:
    window = _make_window()
    window.root.screen_width = 800
    window.root.screen_height = 600
    window.root.root_x = 700
    window.root.root_y = 500
    window.root.root_width = 500
    window.root.root_height = 400

    geometry = support_window.support_jobs._probe_dialog_geometry(window, width=1200, height=900)

    assert geometry == "736x552+64+48"


def test_dialog_wraplength_uses_container_width_with_floor() -> None:
    container = _FakeWidget(width_px=510)

    wrap = support_window.support_jobs._dialog_wraplength(container, padding=72, minimum=220)

    assert wrap == 438


def test_dialog_wraplength_falls_back_to_minimum_for_unmapped_container() -> None:
    container = _FakeWidget(width_px=1)

    wrap = support_window.support_jobs._dialog_wraplength(container, padding=72, minimum=220)

    assert wrap == 220


def test_sync_dialog_prompt_wrap_updates_label() -> None:
    label = _FakeWidget()
    container = _FakeWidget(width_px=510)

    support_window.support_jobs._sync_dialog_prompt_wrap(label, container, padding=72, minimum=220)

    assert label.configure_calls == [{"wraplength": 438}]


def test_build_debug_section_uses_responsive_grid_action_row() -> None:
    registry, fake_ttk, fake_scrolledtext = _build_support_ui_modules()
    window = _make_window()
    parent = _FakeWidget(width_px=640)

    support_window.support_window_ui.build_debug_section(window, parent, ttk=fake_ttk, scrolledtext=fake_scrolledtext)

    row = registry["frames"][0]

    assert row.pack_calls == [{"fill": "x", "pady": (0, 8)}]
    assert row.options["columnconfigure"] == [(0, 1), (1, 1)]
    assert window.btn_copy_debug.grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (0, 0)}]
    assert window.btn_save_debug.grid_calls == [
        {"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (0, 0)}
    ]


def test_build_issue_and_bundle_sections_use_width_friendly_button_rows() -> None:
    registry, fake_ttk, fake_scrolledtext = _build_support_ui_modules()
    window = _make_window()
    issue_parent = _FakeWidget(width_px=640)
    bundle_parent = _FakeWidget(width_px=640)

    support_window.support_window_ui.build_issue_section(window, issue_parent, ttk=fake_ttk, scrolledtext=fake_scrolledtext)
    support_window.support_window_ui.build_bundle_section(window, bundle_parent, ttk=fake_ttk)

    issue_row = registry["frames"][0]
    bundle_row = registry["frames"][1]

    assert issue_row.options["columnconfigure"] == [(0, 1), (1, 1)]
    assert window.btn_copy_issue.grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (0, 0)}]
    assert window.btn_save_issue.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (0, 0)}]
    assert window.btn_collect_evidence.grid_calls == [
        {"row": 1, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (8, 0)}
    ]
    assert window.btn_open_issue.grid_calls == [{"row": 1, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (8, 0)}]
    assert bundle_row.options["columnconfigure"] == [(0, 1)]
    assert window.btn_save_bundle.grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (0, 0)}]


def test_support_probe_dialog_button_row_uses_two_column_grid_for_multiple_actions() -> None:
    registry, fake_ttk = _build_support_jobs_ttk()
    container = _FakeWidget()

    buttons = support_window.support_jobs._build_dialog_button_row(
        container,
        ttk=fake_ttk,
        row=1,
        pady=(18, 0),
        actions=[("Run probe", lambda: None), ("Cancel", lambda: None), ("Help", lambda: None)],
        columns=2,
    )

    row = registry["frames"][0]

    assert row.grid_calls == [{"row": 1, "column": 0, "sticky": "ew", "pady": (18, 0)}]
    assert row.options["columnconfigure"] == [(0, 1), (1, 1)]
    assert buttons[0].grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (0, 0)}]
    assert buttons[1].grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (0, 0)}]
    assert buttons[2].grid_calls == [{"row": 1, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (8, 0)}]


def test_support_probe_dialog_button_row_uses_single_column_for_one_action() -> None:
    registry, fake_ttk = _build_support_jobs_ttk()
    container = _FakeWidget()

    buttons = support_window.support_jobs._build_dialog_button_row(
        container,
        ttk=fake_ttk,
        row=2,
        pady=(12, 0),
        actions=[("OK", lambda: None)],
        columns=2,
    )

    row = registry["frames"][0]

    assert row.grid_calls == [{"row": 2, "column": 0, "sticky": "ew", "pady": (12, 0)}]
    assert row.options["columnconfigure"] == [(0, 1)]
    assert buttons[0].grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 0), "pady": (0, 0)}]


def test_sync_button_state_tracks_copy_and_save_actions() -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"backend": "ite8910"}]}}',
        discovery_json='{"candidate": 1}',
    )
    window._can_run_backend_speed_probe = lambda: True
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


def test_sync_button_state_enables_backend_speed_probe_for_selected_ite8291r3() -> None:
    window = _make_window(diagnostics_json='{"backends": {"selected": "ite8291r3"}}')
    window._can_run_backend_speed_probe = lambda: True

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "normal"


def test_sync_button_state_enables_backend_speed_probe_from_discovery_backend() -> None:
    window = _make_window(discovery_json='{"selected_backend": "ite8291r3"}')
    window._can_run_backend_speed_probe = lambda: True

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "normal"


def test_sync_button_state_disables_backend_speed_probe_without_tray() -> None:
    window = _make_window(diagnostics_json='{"backends": {"selected": "ite8291r3"}}')
    window._can_run_backend_speed_probe = lambda: False

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "disabled"


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


def test_run_discovery_updates_text_and_enables_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window()

    monkeypatch.setattr(
        support_window,
        "collect_device_discovery",
        lambda *, include_usb: {
            "selected_backend": "ite8291r3",
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

    assert json.loads(window._discovery_json)["selected_backend"] == "ite8291r3"
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


def test_run_backend_speed_probe_records_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8910_speed", "backend": "ite8910", "effect_name": "spectrum_cycle", "selection_effect_name": "hw:spectrum_cycle", "selection_menu_path": "Hardware Effects -> Spectrum Cycle", "requested_ui_speeds": [1, 3], "samples": [{"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"}] , "instructions": ["Do the thing"], "observation_prompt": "Notes?"}]}}'
    )
    responses = iter([True, False])
    showinfo_calls: list[str] = []

    class _FakeConfig:
        def __init__(self) -> None:
            self._effect = "color_cycle"
            self._speed = 9
            self._settings = {"effect_speeds": {"spectrum_cycle": 4, "color_cycle": 9}}

        @property
        def effect(self) -> str:
            return self._effect

        @effect.setter
        def effect(self, value: str) -> None:
            self._effect = str(value)

        @property
        def speed(self) -> int:
            return self._speed

        @speed.setter
        def speed(self, value: int) -> None:
            self._speed = int(value)

        def set_effect_speed(self, effect_name: str, speed: int) -> None:
            self._settings.setdefault("effect_speeds", {})[str(effect_name)] = int(speed)

        def _save(self) -> None:
            return

    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: True)
    monkeypatch.setattr(
        support_window.support_jobs,
        "_show_probe_message_dialog",
        lambda _window, *, title, message, **_kwargs: showinfo_calls.append(str(message)) or True,
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_choice_dialog",
        lambda _window, *, title, prompt, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_notes_dialog",
        lambda _window, *, title, prompt, **_kwargs: "1 and 3 looked too close",
    )
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(support_window, "Config", _FakeConfig)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.support_jobs.time, "sleep", lambda _seconds: None)

    window.run_backend_speed_probe(prompt=True)

    assert window._supplemental_evidence is not None
    backend_probes = window._supplemental_evidence.get("backend_probes")
    assert isinstance(backend_probes, dict)
    probe = backend_probes["ite8910_speed"]
    assert probe["backend"] == "ite8910"
    assert probe["selection_effect_name"] == "hw:spectrum_cycle"
    assert probe["execution_mode"] == "auto"
    assert probe["automation"]["step_duration_s"] == 2.5
    assert probe["automation"]["settle_duration_s"] == 0.5
    assert probe["observation"]["distinct_steps"] is False
    assert probe["observation"]["notes"] == "1 and 3 looked too close"
    assert window.status_label.options["text"] == "Backend speed probe recorded"
    assert showinfo_calls
    assert "temporarily switch the tray to the probe effect" in showinfo_calls[0]
    assert "Each speed will stay active for about 2.5 seconds" in showinfo_calls[0]


def test_run_backend_speed_probe_can_auto_run_via_tray_config(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8291r3_speed", "backend": "ite8291r3", "effect_name": "wave", "selection_effect_name": "wave", "selection_menu_path": "Hardware Effects -> Wave", "requested_ui_speeds": [1, 3], "samples": [{"ui_speed": 1, "payload_speed": 10, "raw_speed_hex": "0x0a"}] , "instructions": ["Do the thing"], "observation_prompt": "Notes?"}]}}'
    )
    responses = iter([True, True])
    showinfo_calls: list[str] = []
    sleep_calls: list[float] = []

    class _FakeConfig:
        last_instance = None

        def __init__(self) -> None:
            type(self).last_instance = self
            self._effect = "color_cycle"
            self._speed = 9
            self._settings = {"effect_speeds": {"wave": 4, "color_cycle": 9}}
            self.calls: list[tuple[object, ...]] = []

        @property
        def effect(self) -> str:
            return self._effect

        @effect.setter
        def effect(self, value: str) -> None:
            self._effect = str(value)
            self.calls.append(("effect", str(value)))

        @property
        def speed(self) -> int:
            return self._speed

        @speed.setter
        def speed(self, value: int) -> None:
            self._speed = int(value)
            self.calls.append(("speed", int(value)))

        def set_effect_speed(self, effect_name: str, speed: int) -> None:
            self._settings.setdefault("effect_speeds", {})[str(effect_name)] = int(speed)
            self.calls.append(("set_effect_speed", str(effect_name), int(speed)))

        def _save(self) -> None:
            self.calls.append(("save_effect_speeds", dict(self._settings.get("effect_speeds", {}))))

    monkeypatch.setenv("KEYRGB_TRAY_PID", "1234")
    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: True)
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_choice_dialog",
        lambda _window, *, title, prompt, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_show_probe_message_dialog",
        lambda _window, *, title, message, **_kwargs: showinfo_calls.append(str(message)) or True,
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_notes_dialog",
        lambda _window, *, title, prompt, **_kwargs: "looked distinct",
    )
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(support_window, "Config", _FakeConfig)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.support_jobs.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    window.run_backend_speed_probe(prompt=True)

    probe = window._supplemental_evidence["backend_probes"]["ite8291r3_speed"]
    assert probe["execution_mode"] == "auto"
    assert probe["automation"]["step_duration_s"] == 2.5
    assert probe["automation"]["settle_duration_s"] == 0.5
    assert probe["observation"]["distinct_steps"] is True
    assert probe["observation"]["notes"] == "looked distinct"
    assert probe["automation"]["applied_ui_speeds"] == [1, 3]
    assert sleep_calls == [0.5, 2.5, 2.5, 0.5]
    assert _FakeConfig.last_instance is not None
    assert _FakeConfig.last_instance.calls == [
        ("effect", "wave"),
        ("set_effect_speed", "wave", 1),
        ("speed", 1),
        ("set_effect_speed", "wave", 3),
        ("speed", 3),
        ("save_effect_speeds", {"wave": 4, "color_cycle": 9}),
        ("speed", 9),
        ("effect", "color_cycle"),
    ]
    assert showinfo_calls
    assert "temporarily switch the tray to the probe effect" in showinfo_calls[0]
    assert "Each speed will stay active for about 2.5 seconds" in showinfo_calls[0]


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
                "backend": "ite8910",
                "effect_name": "spectrum_cycle",
            }
        }
    }


def test_run_backend_speed_probe_requires_running_tray(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8291r3_speed", "backend": "ite8291r3", "effect_name": "wave"}]}}'
    )

    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: False)

    window.run_backend_speed_probe(prompt=False)

    assert window._supplemental_evidence is None
    assert window.status_label.options["text"] == "Backend speed probe requires the running tray session"


def test_set_status_clears_message_after_delay() -> None:
    window = _make_window()

    window._set_status("Ready", ok=True)

    assert window.status_label.options["text"] == "Ready"
    _flush_after(window.root)
    assert window.status_label.options["text"] == ""
