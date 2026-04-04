from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.ui.calibrator import run_keymap_calibrator_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


@dataclass
class DummyEditor:
    status_label: DummyLabel


def test_run_keymap_calibrator_ui_sets_started_message_on_success() -> None:
    ed = DummyEditor(status_label=DummyLabel())

    def ok() -> None:
        return

    run_keymap_calibrator_ui(ed, launch_fn=ok)

    assert ed.status_label.text == "Calibrator started — map keys then Save"


def test_run_keymap_calibrator_ui_sets_failed_message_on_exception() -> None:
    ed = DummyEditor(status_label=DummyLabel())

    def boom() -> None:
        raise RuntimeError("nope")

    run_keymap_calibrator_ui(ed, launch_fn=boom)

    assert ed.status_label.text.startswith("Failed to start calibrator")
    assert "Try:" in ed.status_label.text
