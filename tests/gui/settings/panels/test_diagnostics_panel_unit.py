from __future__ import annotations

import webbrowser

import pytest

import src.gui.settings.panels.diagnostics_panel as diagnostics_panel


class _FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.options: dict[str, object] = dict(kwargs)
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)


class _FakeText(_FakeWidget):
    def __init__(self, text: str = "") -> None:
        super().__init__(state="disabled")
        self.contents = text
        self.delete_calls: list[tuple[str, str]] = []
        self.insert_calls: list[tuple[str, str]] = []

    def delete(self, start: str, end: str) -> None:
        self.delete_calls.append((start, end))
        self.contents = ""

    def insert(self, index: str, value: str) -> None:
        self.insert_calls.append((index, value))
        self.contents = value


class _FakeRoot:
    def __init__(self) -> None:
        self.clipboard_cleared = 0
        self.clipboard_values: list[str] = []
        self.after_calls: list[tuple[int, object]] = []

    def clipboard_clear(self) -> None:
        self.clipboard_cleared += 1

    def clipboard_append(self, value: str) -> None:
        self.clipboard_values.append(value)

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))


def _flush_after(root: _FakeRoot) -> None:
    callbacks = list(root.after_calls)
    for _delay_ms, callback in callbacks:
        callback()


def _make_panel(
    *,
    diagnostics_json: str = "",
    get_status_label=None,
) -> tuple[diagnostics_panel.DiagnosticsPanel, _FakeRoot, _FakeWidget]:
    root = _FakeRoot()
    status_label = _FakeWidget(text="")
    panel = diagnostics_panel.DiagnosticsPanel.__new__(diagnostics_panel.DiagnosticsPanel)
    panel._root = root
    panel._get_status_label = get_status_label or (lambda: status_label)
    panel._bg_color = "#000000"
    panel._fg_color = "#ffffff"
    panel._diagnostics_json = diagnostics_json
    panel.btn_run_diagnostics = _FakeWidget(state="normal")
    panel.btn_copy_diagnostics = _FakeWidget(state="disabled")
    panel.btn_open_issue = _FakeWidget(state="normal")
    panel.txt_diagnostics = _FakeText("stale output")
    return panel, root, status_label


@pytest.mark.parametrize(
    ("diagnostics_json", "expected_state"),
    [
        ("", "disabled"),
        ('{"status": "ok"}', "normal"),
    ],
)
def test_apply_state_updates_copy_button_from_json_presence(diagnostics_json: str, expected_state: str) -> None:
    panel, _root, _status = _make_panel(diagnostics_json=diagnostics_json)

    panel.apply_state()

    assert panel.btn_copy_diagnostics.configure_calls == [{"state": expected_state}]
    assert panel.btn_copy_diagnostics.options["state"] == expected_state


def test_status_returns_none_when_status_lookup_raises() -> None:
    def raise_status_lookup():
        raise RuntimeError("status failed")

    panel, _root, _status = _make_panel(get_status_label=raise_status_lookup)

    assert panel._status() is None


def test_set_text_replaces_existing_contents_and_restores_disabled_state() -> None:
    panel, _root, _status = _make_panel()

    panel._set_text("fresh output")

    assert panel.txt_diagnostics.configure_calls == [{"state": "normal"}, {"state": "disabled"}]
    assert panel.txt_diagnostics.delete_calls == [("1.0", "end")]
    assert panel.txt_diagnostics.insert_calls == [("1.0", "fresh output")]
    assert panel.txt_diagnostics.contents == "fresh output"
    assert panel.txt_diagnostics.options["state"] == "disabled"


def test_copy_output_copies_json_and_reports_success() -> None:
    panel, root, status_label = _make_panel(diagnostics_json='{"status": "ok"}')

    panel.copy_output()

    assert root.clipboard_cleared == 1
    assert root.clipboard_values == ['{"status": "ok"}']
    assert status_label.options["text"] == "✓ Copied to clipboard"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [1500]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_copy_output_ignores_tk_clipboard_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    panel, root, status_label = _make_panel(diagnostics_json='{"status": "ok"}')

    def fail_clipboard_clear() -> None:
        raise diagnostics_panel.tk.TclError("clipboard busy")

    def fail_clipboard_append(_value: str) -> None:
        raise AssertionError("clipboard_append should not be called after clipboard_clear fails")

    monkeypatch.setattr(root, "clipboard_clear", fail_clipboard_clear)
    monkeypatch.setattr(root, "clipboard_append", fail_clipboard_append)

    panel.copy_output()

    assert status_label.options["text"] == "✓ Copied to clipboard"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [1500]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_copy_output_requires_existing_diagnostics_json() -> None:
    panel, root, status_label = _make_panel(diagnostics_json="")

    panel.copy_output()

    assert root.clipboard_cleared == 0
    assert root.clipboard_values == []
    assert status_label.options["text"] == "Run diagnostics first"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [1500]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_open_issue_form_reports_success_when_browser_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[tuple[str, int]] = []

    def fake_open(url: str, new: int = 0) -> bool:
        opened.append((url, new))
        return True

    monkeypatch.setattr(diagnostics_panel.webbrowser, "open", fake_open)
    panel, root, status_label = _make_panel()

    panel.open_issue_form()

    assert opened == [("https://github.com/Rainexn0b/keyRGB/issues/new/choose", 2)]
    assert root.clipboard_cleared == 0
    assert root.clipboard_values == []
    assert status_label.options["text"] == "Opened issue form"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [2000]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_open_issue_form_copies_url_when_browser_open_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(_url: str, new: int = 0) -> bool:
        assert new == 2
        raise OSError("no browser")

    monkeypatch.setattr(diagnostics_panel.webbrowser, "open", fake_open)
    panel, root, status_label = _make_panel()

    panel.open_issue_form()

    assert root.clipboard_cleared == 1
    assert root.clipboard_values == ["https://github.com/Rainexn0b/keyRGB/issues/new/choose"]
    assert status_label.options["text"] == "Couldn't open browser (URL copied)"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [2000]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_open_issue_form_ignores_tk_clipboard_failures_after_browser_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_open(_url: str, new: int = 0) -> bool:
        assert new == 2
        raise webbrowser.Error("no browser")

    def fail_clipboard_clear() -> None:
        raise diagnostics_panel.tk.TclError("clipboard busy")

    monkeypatch.setattr(diagnostics_panel.webbrowser, "open", fake_open)
    panel, root, status_label = _make_panel()
    monkeypatch.setattr(root, "clipboard_clear", fail_clipboard_clear)

    panel.open_issue_form()

    assert root.clipboard_values == []
    assert status_label.options["text"] == "Couldn't open browser (URL copied)"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [2000]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_run_diagnostics_keeps_json_output_and_enables_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostics_json = '{\n  "warnings": ["usb busy"]\n}'
    seen: dict[str, object] = {}

    def fake_collect_diagnostics_text(*, include_usb: bool) -> str:
        seen["include_usb"] = include_usb
        return diagnostics_json

    def fake_run_in_thread(root, work, on_done) -> None:
        seen["root"] = root
        seen["status_before_work"] = status_label.options["text"]
        seen["run_state_before_work"] = panel.btn_run_diagnostics.options["state"]
        seen["copy_state_before_work"] = panel.btn_copy_diagnostics.options["state"]
        result = work()
        seen["work_result"] = result
        on_done(result)

    monkeypatch.setattr(diagnostics_panel, "collect_diagnostics_text", fake_collect_diagnostics_text)
    monkeypatch.setattr(diagnostics_panel, "run_in_thread", fake_run_in_thread)
    panel, root, status_label = _make_panel()

    panel.run_diagnostics()

    assert seen == {
        "include_usb": True,
        "root": root,
        "status_before_work": "Collecting diagnostics…",
        "run_state_before_work": "disabled",
        "copy_state_before_work": "disabled",
        "work_result": diagnostics_json,
    }
    assert panel._diagnostics_json == diagnostics_json
    assert panel.txt_diagnostics.contents == diagnostics_json
    assert panel.btn_run_diagnostics.options["state"] == "normal"
    assert panel.btn_copy_diagnostics.options["state"] == "normal"
    assert status_label.options["text"] == "⚠ Diagnostics ready (warnings)"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [2000]

    _flush_after(root)

    assert status_label.options["text"] == ""


def test_run_diagnostics_formats_failure_text_and_leaves_copy_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_collect_diagnostics_text(*, include_usb: bool) -> str:
        seen["include_usb"] = include_usb
        raise LookupError("boom")

    def fake_run_in_thread(root, work, on_done) -> None:
        seen["root"] = root
        result = work()
        seen["work_result"] = result
        on_done(result)

    monkeypatch.setattr(diagnostics_panel, "collect_diagnostics_text", fake_collect_diagnostics_text)
    monkeypatch.setattr(diagnostics_panel, "run_in_thread", fake_run_in_thread)
    panel, root, status_label = _make_panel()

    panel.run_diagnostics()

    assert seen == {
        "include_usb": True,
        "root": root,
        "work_result": "Failed to collect diagnostics: boom",
    }
    assert panel._diagnostics_json == ""
    assert panel.txt_diagnostics.contents == "Failed to collect diagnostics: boom"
    assert panel.btn_run_diagnostics.options["state"] == "normal"
    assert panel.btn_copy_diagnostics.options["state"] == "disabled"
    assert status_label.options["text"] == "✓ Diagnostics ready"
    assert [delay_ms for delay_ms, _callback in root.after_calls] == [2000]

    _flush_after(root)

    assert status_label.options["text"] == ""
