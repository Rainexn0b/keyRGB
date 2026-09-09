from __future__ import annotations

from dataclasses import dataclass

import pytest

from keyrgb.gui.perkey.ui.calibrator import run_keymap_calibrator_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


class DummyRoot:
    def __init__(self, *, exists: bool = True) -> None:
        self.after_calls: list[tuple[int, object]] = []
        self.exists = exists

    def after(self, delay_ms: int, callback: object) -> None:
        self.after_calls.append((delay_ms, callback))

    def winfo_exists(self) -> int:
        return int(self.exists)


class DummyProcess:
    def __init__(self, poll_results: list[int | None]) -> None:
        self._poll_results = iter(poll_results)

    def poll(self) -> int | None:
        return next(self._poll_results)


@dataclass
class DummyEditor:
    root: DummyRoot
    status_label: DummyLabel
    reload_calls: int = 0

    def _reload_keymap(self) -> None:
        self.reload_calls += 1


def test_run_keymap_calibrator_ui_sets_started_message_on_success() -> None:
    ed = DummyEditor(root=DummyRoot(), status_label=DummyLabel())
    process = DummyProcess([None, 0])

    def ok() -> DummyProcess:
        return process

    run_keymap_calibrator_ui(ed, launch_fn=ok)

    assert ed.status_label.text == "Calibrator started — map keys then Save"
    assert ed.reload_calls == 0
    assert ed.root.after_calls[0][0] == 250

    first_poll = ed.root.after_calls.pop(0)[1]
    assert callable(first_poll)
    first_poll()
    assert ed.reload_calls == 0
    assert ed.root.after_calls[0][0] == 250

    final_poll = ed.root.after_calls.pop(0)[1]
    assert callable(final_poll)
    final_poll()
    assert ed.reload_calls == 1


def test_run_keymap_calibrator_ui_sets_failed_message_on_exception() -> None:
    ed = DummyEditor(root=DummyRoot(), status_label=DummyLabel())

    def boom() -> DummyProcess:
        raise RuntimeError("nope")

    run_keymap_calibrator_ui(ed, launch_fn=boom)

    assert ed.status_label.text.startswith("Failed to start calibrator")
    assert "Try:" in ed.status_label.text
    assert ed.root.after_calls == []


def test_run_keymap_calibrator_ui_propagates_unexpected_failures() -> None:
    ed = DummyEditor(root=DummyRoot(), status_label=DummyLabel())

    def boom() -> DummyProcess:
        raise AssertionError("nope")

    with pytest.raises(AssertionError):
        run_keymap_calibrator_ui(ed, launch_fn=boom)


def test_calibrator_poll_stops_after_editor_teardown() -> None:
    ed = DummyEditor(root=DummyRoot(exists=False), status_label=DummyLabel())
    process = DummyProcess([0])

    run_keymap_calibrator_ui(ed, launch_fn=lambda: process)
    poll = ed.root.after_calls.pop()[1]
    assert callable(poll)
    poll()

    assert ed.reload_calls == 0
    assert ed.root.after_calls == []
