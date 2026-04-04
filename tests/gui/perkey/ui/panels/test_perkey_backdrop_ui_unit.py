from __future__ import annotations

from dataclasses import dataclass

import pytest

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


class FailingCanvas(DummyCanvas):
    def reload_backdrop_image(self) -> None:
        raise RuntimeError("reload boom")


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
    saved_modes: list[tuple[str, str]] = []

    def ask(**_kwargs) -> str:
        return "/tmp/backdrop.png"

    def save_fn(*, profile_name: str, source_path: str) -> None:
        saved["profile_name"] = profile_name
        saved["source_path"] = source_path

    set_backdrop_ui(
        ed,
        askopenfilename=ask,
        save_fn=save_fn,
        save_mode_fn=lambda mode, name: saved_modes.append((str(mode), str(name))),
    )

    assert saved == {"profile_name": "p1", "source_path": "/tmp/backdrop.png"}
    assert saved_modes == [("custom", "p1")]
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


def test_set_backdrop_ui_sets_failed_status_when_reload_raises_runtime_error() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=FailingCanvas())

    def ask(**_kwargs) -> str:
        return "/tmp/backdrop.png"

    set_backdrop_ui(
        ed,
        askopenfilename=ask,
        save_fn=lambda **_kwargs: None,
        save_mode_fn=lambda *_args: None,
    )

    assert ed.status_label.text.startswith("Failed to set backdrop")
    assert "Try:" in ed.status_label.text


def test_set_backdrop_ui_propagates_unexpected_type_error() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    def ask(**_kwargs) -> str:
        return "/tmp/backdrop.png"

    def save_mode_fn(*_args) -> None:
        raise TypeError("unexpected bug")

    with pytest.raises(TypeError, match="unexpected bug"):
        set_backdrop_ui(
            ed,
            askopenfilename=ask,
            save_fn=lambda **_kwargs: None,
            save_mode_fn=save_mode_fn,
        )


def test_reset_backdrop_ui_sets_status_and_reloads_on_success() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=DummyCanvas())

    called = {"name": None}
    saved_modes: list[tuple[str, str]] = []

    def reset_fn(name: str) -> None:
        called["name"] = name

    reset_backdrop_ui(
        ed,
        reset_fn=reset_fn,
        save_mode_fn=lambda mode, name: saved_modes.append((str(mode), str(name))),
    )

    assert called["name"] == "p1"
    assert saved_modes == [("builtin", "p1")]
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


def test_reset_backdrop_ui_sets_failed_status_when_reload_raises_runtime_error() -> None:
    ed = DummyEditor(profile_name="p1", status_label=DummyLabel(), canvas=FailingCanvas())

    reset_backdrop_ui(
        ed,
        reset_fn=lambda _name: None,
        save_mode_fn=lambda *_args: None,
    )

    assert ed.status_label.text.startswith("Failed to reset backdrop")
    assert "Try:" in ed.status_label.text
