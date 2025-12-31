from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.wheel_apply_ui import on_wheel_color_change_ui, on_wheel_color_release_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


class DummyCanvas:
    def __init__(self):
        self.redraw_calls = 0
        self.last_visual = None

    def redraw(self) -> None:
        self.redraw_calls += 1

    def update_key_visual(self, key_id: str, color: tuple[int, int, int]) -> None:
        self.last_visual = (key_id, color)


class DummyBool:
    def __init__(self, v: bool):
        self.v = v

    def get(self) -> bool:
        return self.v


@dataclass
class DummyEditor:
    colors: dict
    selected_key_id: str | None
    selected_cell: tuple[int, int] | None
    apply_all_keys: DummyBool
    canvas: DummyCanvas
    status_label: DummyLabel
    _last_non_black_color: tuple[int, int, int]

    commit_calls: list[bool]

    def _commit(self, *, force: bool) -> None:
        self.commit_calls.append(bool(force))


def test_on_wheel_color_change_ui_no_selection_no_allkeys_returns() -> None:
    ed = DummyEditor(
        colors={},
        selected_key_id=None,
        selected_cell=None,
        apply_all_keys=DummyBool(False),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _last_non_black_color=(9, 9, 9),
        commit_calls=[],
    )

    called = {"apply": 0}

    def apply_fn(**_kwargs):
        called["apply"] += 1
        return {}

    on_wheel_color_change_ui(ed, 1, 2, 3, num_rows=1, num_cols=1, apply_fn=apply_fn)

    assert called["apply"] == 0
    assert ed.canvas.redraw_calls == 0
    assert ed.canvas.last_visual is None
    assert ed.commit_calls == []


def test_on_wheel_color_change_ui_updates_single_key_and_commits_soft() -> None:
    ed = DummyEditor(
        colors={(0, 0): (0, 0, 0)},
        selected_key_id="K1",
        selected_cell=(0, 0),
        apply_all_keys=DummyBool(False),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _last_non_black_color=(0, 0, 0),
        commit_calls=[],
    )

    def apply_fn(*, colors, num_rows: int, num_cols: int, color, apply_all_keys: bool, selected_cell):
        assert (num_rows, num_cols) == (3, 4)
        assert apply_all_keys is False
        assert selected_cell == (0, 0)
        assert color == (1, 2, 3)
        # ensure we were passed a copy
        assert colors == {(0, 0): (0, 0, 0)}
        return {(0, 0): (1, 2, 3)}

    on_wheel_color_change_ui(ed, 1, 2, 3, num_rows=3, num_cols=4, apply_fn=apply_fn)

    assert ed.colors == {(0, 0): (1, 2, 3)}
    assert ed._last_non_black_color == (1, 2, 3)
    assert ed.canvas.last_visual == ("K1", (1, 2, 3))
    assert ed.canvas.redraw_calls == 0
    assert ed.commit_calls == [False]
    assert ed.status_label.text == ""


def test_on_wheel_color_release_ui_all_keys_sets_status_and_commits_hard() -> None:
    ed = DummyEditor(
        colors={},
        selected_key_id=None,
        selected_cell=None,
        apply_all_keys=DummyBool(True),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _last_non_black_color=(0, 0, 0),
        commit_calls=[],
    )

    def apply_fn(**_kwargs):
        return {(0, 0): (1, 2, 3)}

    on_wheel_color_release_ui(ed, 1, 2, 3, num_rows=2, num_cols=2, apply_fn=apply_fn)

    assert ed.canvas.redraw_calls == 1
    assert ed.commit_calls == [True]
    assert ed.status_label.text == "Saved all keys = RGB(1,2,3)"


def test_on_wheel_color_release_ui_single_key_sets_status() -> None:
    ed = DummyEditor(
        colors={},
        selected_key_id="K7",
        selected_cell=(1, 1),
        apply_all_keys=DummyBool(False),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _last_non_black_color=(0, 0, 0),
        commit_calls=[],
    )

    def apply_fn(**_kwargs):
        return {(1, 1): (4, 5, 6)}

    on_wheel_color_release_ui(ed, 4, 5, 6, num_rows=9, num_cols=9, apply_fn=apply_fn)

    assert ed.canvas.last_visual == ("K7", (4, 5, 6))
    assert ed.commit_calls == [True]
    assert ed.status_label.text == "Saved K7 = RGB(4,5,6)"
