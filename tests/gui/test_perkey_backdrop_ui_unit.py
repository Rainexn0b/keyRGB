from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.ui.backdrop import reset_backdrop_ui, set_backdrop_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


class DummyCanvas:
    def __init__(self):
        self.reload_calls = 0

    def reload_backdrop_image(self) -> None:
        self.reload_calls += 1


@dataclass
class DummyEditor:
    profile_name: str
    status_label: DummyLabel
    canvas: DummyCanvas


def test_set_backdrop_ui_returns_when_no_path_selected() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    called = {"save": 0}

    def ask(**_kwargs) -> str:
        return ""

    def save_fn(**_kwargs) -> None:
        called["save"] += 1

    ed.status_label.text = "Existing"
    set_backdrop_ui(ed, askopenfilename=ask, save_fn=save_fn)

    assert called["save"] == 0
    assert ed.canvas.reload_calls == 0
    assert ed.status_label.text == "Existing"


def test_set_backdrop_ui_sets_status_and_reloads_on_success() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    saved = {}

    def ask(**_kwargs) -> str:
        return "/tmp/backdrop.png"

    def save_fn(*, profile_name: str, source_path: str) -> None:
        saved["profile_name"] = profile_name
        saved["source_path"] = source_path

    set_backdrop_ui(ed, askopenfilename=ask, save_fn=save_fn)

    assert saved == {"profile_name": "p1", "source_path": "/tmp/backdrop.png"}
    assert ed.canvas.reload_calls == 1
    assert ed.status_label.text == "Backdrop updated"


def test_set_backdrop_ui_sets_failed_status_on_exception() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    def ask(**_kwargs) -> str:
        return "/tmp/backdrop.png"

    def save_fn(**_kwargs) -> None:
        raise RuntimeError("boom")

    set_backdrop_ui(ed, askopenfilename=ask, save_fn=save_fn)

    assert ed.canvas.reload_calls == 0
    assert ed.status_label.text.startswith("Failed to set backdrop")
    assert "Try:" in ed.status_label.text


def test_reset_backdrop_ui_sets_status_and_reloads_on_success() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    called = {"name": None}

    def reset_fn(name: str) -> None:
        called["name"] = name

    reset_backdrop_ui(ed, reset_fn=reset_fn)

    assert called["name"] == "p1"
    assert ed.canvas.reload_calls == 1
    assert ed.status_label.text == "Backdrop reset"


def test_reset_backdrop_ui_sets_failed_status_on_exception() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    def reset_fn(_name: str) -> None:
        raise RuntimeError("boom")

    reset_backdrop_ui(ed, reset_fn=reset_fn)

    assert ed.canvas.reload_calls == 0
    assert ed.status_label.text.startswith("Failed to reset backdrop")
    assert "Try:" in ed.status_label.text
