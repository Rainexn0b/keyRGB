from __future__ import annotations

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.gui.windows.support as support_window
from tests.gui.windows._support_window_test_fakes import (
    FakeRoot as _FakeRoot,
    FakeText as _FakeText,
    FakeWidget as _FakeWidget,
    build_support_jobs_ttk as _build_support_jobs_ttk,
    build_support_ui_modules as _build_support_ui_modules,
    flush_after as _flush_after,
    make_window as _make_window,
)


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
    assert isinstance(window._support_session, support_window.support_window_state.SupportSessionState)
    assert window._diagnostics_json == ""
    assert window._discovery_json == ""
    assert window.root.title_text == "KeyRGB - Support Tools"
    assert window.root.minsize_value == (960, 720)
    assert window.btn_run_debug.options["style"] == "SupportChecks.Diagnostics.TButton"
    assert window.btn_run_speed_probe.options["style"] == "SupportChecks.Probe.TButton"
    assert window.btn_run_discovery.options["style"] == "SupportChecks.Discovery.TButton"
    assert any(delay == 50 for delay, _callback in window.root.after_calls)


def test_legacy_support_state_bridge_creates_session_when_init_is_bypassed() -> None:
    window = support_window.SupportToolsGUI.__new__(support_window.SupportToolsGUI)

    window._diagnostics_json = '{"ok": true}'
    window._discovery_json = '{"candidate": 1}'
    window._supplemental_evidence = {"captures": {"lsusb_verbose": {"ok": True}}}
    window._issue_report = {"markdown": "issue draft"}
    window._capture_prompt_key = "048d:ce00:lsusb_verbose"
    window._backend_probe_prompt_key = "ite8291r3_speed:ite8291r3_perkey"

    assert isinstance(window._support_session, support_window.support_window_state.SupportSessionState)
    assert window._diagnostics_json == '{"ok": true}'
    assert window._discovery_json == '{"candidate": 1}'
    assert window._supplemental_evidence == {"captures": {"lsusb_verbose": {"ok": True}}}
    assert window._issue_report == {"markdown": "issue draft"}
    assert window._capture_prompt_key == "048d:ce00:lsusb_verbose"
    assert window._backend_probe_prompt_key == "ite8291r3_speed:ite8291r3_perkey"


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
        diagnostics_json='{"backends": {"guided_speed_probes": [{"backend": "ite8910_perkey"}]}}',
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
    window = _make_window(diagnostics_json='{"backends": {"selected": "ite8291r3_perkey"}}')
    window._can_run_backend_speed_probe = lambda: True

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "normal"


def test_sync_button_state_enables_backend_speed_probe_from_discovery_backend() -> None:
    window = _make_window(discovery_json='{"selected_backend": "ite8291r3_perkey"}')
    window._can_run_backend_speed_probe = lambda: True

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "normal"


def test_sync_button_state_disables_backend_speed_probe_without_tray() -> None:
    window = _make_window(diagnostics_json='{"backends": {"selected": "ite8291r3_perkey"}}')
    window._can_run_backend_speed_probe = lambda: False

    window._sync_button_state()

    assert window.btn_run_speed_probe.options["state"] == "disabled"


def test_set_status_clears_message_after_delay() -> None:
    window = _make_window()

    window._set_status("Ready", ok=True)

    assert window.status_label.options["text"] == "Ready"
    _flush_after(window.root)
    assert window.status_label.options["text"] == ""
