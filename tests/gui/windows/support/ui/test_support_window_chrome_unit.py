"""Support window chrome: init, state bridge, geometry, focus, and shortcuts."""

from __future__ import annotations

import pytest

import keyrgb.gui.windows.support as support_window
from tests.gui.windows.support._support_window_test_fakes import (
    FakeRoot as _FakeRoot,
    FakeText as _FakeText,
    FakeWidget as _FakeWidget,
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


def test_build_window_uses_semantic_styles_and_preserves_env_focus_contract() -> None:
    from keyrgb.gui.theme import metrics as theme_metrics

    registry, fake_ttk, fake_scrolledtext = _build_support_ui_modules()

    class _FakeStyle:
        def __init__(self, *args, **kwargs) -> None:
            self.configured: list[tuple[str, dict[str, object]]] = []
            self.mapped: list[tuple[str, dict[str, object]]] = []

        def configure(self, name: str, **kwargs) -> None:
            self.configured.append((name, dict(kwargs)))

        def map(self, name: str, **kwargs) -> None:
            self.mapped.append((name, dict(kwargs)))

    fake_ttk.LabelFrame = fake_ttk.Frame
    style_holder: dict[str, _FakeStyle] = {}

    def _make_style(*args, **kwargs) -> _FakeStyle:
        style = _FakeStyle()
        style_holder["style"] = style
        return style

    fake_ttk.Style = _make_style  # type: ignore[attr-defined]

    window = _make_window()
    support_window.support_window_ui.build_window(
        window,
        ttk=fake_ttk,
        scrolledtext=fake_scrolledtext,
        center_window_on_screen=lambda root: None,
    )

    assert window._main_frame.options["padding"] == theme_metrics.OUTER_PADDING

    title_label = registry["labels"][0]
    assert title_label.options["text"] == "Support Tools"
    assert title_label.options["style"] == theme_metrics.TITLE_LABEL_STYLE
    assert all("font" not in label.options for label in registry["labels"])

    intro_label = registry["labels"][1]
    assert intro_label.options["style"] == theme_metrics.BODY_LABEL_STYLE
    assert window.status_label.options["style"] == theme_metrics.STATUS_LABEL_STYLE
    assert window.issue_meta_label.options["text"].startswith("Suggested template")
    assert window.issue_meta_label.options["style"] == theme_metrics.STATUS_LABEL_STYLE
    caption_labels = [label for label in registry["labels"] if label.options.get("wraplength") == 300]
    assert len(caption_labels) == 3
    assert all(label.options["style"] == theme_metrics.CAPTION_LABEL_STYLE for label in caption_labels)

    # The status-palette run-check styles are retained, not replaced by generic actions.
    assert window.btn_run_debug.options["style"] == "SupportChecks.Diagnostics.TButton"
    assert window.btn_run_speed_probe.options["style"] == "SupportChecks.Probe.TButton"
    assert window.btn_run_discovery.options["style"] == "SupportChecks.Discovery.TButton"
    configured_names = [name for name, _kwargs in style_holder["style"].configured]
    assert configured_names == [
        "SupportChecks.Diagnostics.TButton",
        "SupportChecks.Probe.TButton",
        "SupportChecks.Discovery.TButton",
    ]
    assert "style" not in window.btn_copy_debug.options
    assert "style" not in window.btn_save_bundle.options

    # Env-driven focus uses the shared non-forcing scheduler.
    assert [delay for delay, _callback in window.root.after_calls] == [0, 50]
    _delay, focus_callback = window.root.after_calls[1]
    assert callable(focus_callback)
    focus_callback()
    assert window.btn_run_debug.options["focused"] is True
    assert "focused" not in window.txt_debug.options


def test_support_initial_focus_targets_discovery_action_without_stealing_existing_focus() -> None:
    window = _make_window()
    support_window.support_window_ui.apply_initial_focus(
        window,
        focus_env="discovery",
    )

    delay, focus_callback = window.root.after_calls[-1]
    assert delay == 50
    assert callable(focus_callback)
    window.root.focused = object()
    focus_callback()

    assert "focused" not in window.btn_run_discovery.options
    assert "focused" not in window.txt_discovery.options


def test_set_status_clears_message_after_delay() -> None:
    window = _make_window()

    window._set_status("Ready", ok=True)

    assert window.status_label.options["text"] == "Ready"
    _flush_after(window.root)
    assert window.status_label.options["text"] == ""


def test_shortcuts_route_to_orderly_close_without_save(monkeypatch: pytest.MonkeyPatch) -> None:
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
    root = created_roots[0]

    # WM protocol is preserved on the exact orderly close path.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", window._on_close)]
    # Exact shortcut set: close-only, additive, no save, no native navigation.
    assert [sequence for sequence, _, _ in root.bind_calls] == ["<Control-w>", "<Escape>"]
    assert all(add == "+" for _, _, add in root.bind_calls)
    assert all("Tab" not in sequence for sequence, _, _ in root.bind_calls)
    assert root.bind_calls[0][1] is root.bind_calls[1][1]
    # Existing close/geometry ordering stays: delayed centered pass still runs.
    assert any(delay == 50 for delay, _callback in root.after_calls)
    assert root.bind_calls[0][1](object()) == "break"
    assert root.destroy_calls == 1
