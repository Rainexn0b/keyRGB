from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.ui.keymap import reload_keymap_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


class DummyCanvas:
    def __init__(self):
        self.redraw_calls = 0

    def redraw(self) -> None:
        self.redraw_calls += 1


@dataclass
class DummyEditor:
    keymap: dict
    selected_key_id: str | None
    selected_cell: tuple[int, int] | None
    status_label: DummyLabel
    canvas: DummyCanvas

    next_keymap: dict

    def _load_keymap(self):
        return dict(self.next_keymap)


def test_reload_keymap_ui_updates_selection_and_sets_status_on_change() -> None:
    ed = DummyEditor(
        keymap={},
        selected_key_id="K1",
        selected_cell=None,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        next_keymap={"K1": (1, 2)},
    )

    reload_keymap_ui(ed)

    assert ed.keymap == {"K1": (1, 2)}
    assert ed.selected_cell == (1, 2)
    assert ed.status_label.text == "Keymap reloaded"
    assert ed.canvas.redraw_calls == 1


def test_reload_keymap_ui_sets_no_keymap_status_when_keymap_becomes_empty() -> None:
    ed = DummyEditor(
        keymap={"K1": (1, 2)},
        selected_key_id="K1",
        selected_cell=(1, 2),
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        next_keymap={},
    )

    reload_keymap_ui(ed)

    assert ed.keymap == {}
    assert ed.selected_cell is None
    assert ed.status_label.text == "No keymap found — run Keymap Calibrator"
    assert ed.canvas.redraw_calls == 1


def test_reload_keymap_ui_does_not_touch_status_when_unchanged() -> None:
    ed = DummyEditor(
        keymap={"K1": (1, 2)},
        selected_key_id="K1",
        selected_cell=(1, 2),
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        next_keymap={"K1": (1, 2)},
    )
    ed.status_label.text = "Existing"

    reload_keymap_ui(ed)

    assert ed.keymap == {"K1": (1, 2)}
    assert ed.selected_cell == (1, 2)
    assert ed.status_label.text == "Existing"
    assert ed.canvas.redraw_calls == 1
