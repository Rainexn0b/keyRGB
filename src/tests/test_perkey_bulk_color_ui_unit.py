from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.bulk_color_ui import clear_all_ui, fill_all_ui


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


class DummyWheel:
    def __init__(self, rgb: tuple[int, int, int]):
        self.rgb = rgb

    def get_color(self) -> tuple[int, int, int]:
        return self.rgb


@dataclass
class DummyConfig:
    brightness: int
    effect: str | None = None
    per_key_colors: dict | None = None


@dataclass
class DummyEditor:
    color_wheel: DummyWheel
    canvas: DummyCanvas
    status_label: DummyLabel
    config: DummyConfig
    kb: object
    colors: dict

    commit_calls: list[bool]

    def _commit(self, *, force: bool) -> None:
        self.commit_calls.append(bool(force))


def test_fill_all_ui_fills_redraws_commits_and_sets_status() -> None:
    ed = DummyEditor(
        color_wheel=DummyWheel((1, 2, 3)),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        config=DummyConfig(brightness=50),
        kb=object(),
        colors={},
        commit_calls=[],
    )

    def fill_fn(*, num_rows: int, num_cols: int, color: tuple[int, int, int]) -> dict:
        assert (num_rows, num_cols) == (3, 4)
        assert color == (1, 2, 3)
        return {(0, 0): (1, 2, 3)}

    fill_all_ui(ed, num_rows=3, num_cols=4, fill_fn=fill_fn)

    assert ed.colors == {(0, 0): (1, 2, 3)}
    assert ed.canvas.redraw_calls == 1
    assert ed.commit_calls == [True]
    assert ed.status_label.text == "Filled all keys = RGB(1,2,3)"


def test_clear_all_ui_clears_redraws_pushes_and_sets_status() -> None:
    kb0 = object()
    kb1 = object()

    ed = DummyEditor(
        color_wheel=DummyWheel((0, 0, 0)),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        config=DummyConfig(brightness=77),
        kb=kb0,
        colors={(0, 0): (9, 9, 9)},
        commit_calls=[],
    )

    def clear_fn(*, num_rows: int, num_cols: int) -> dict:
        assert (num_rows, num_cols) == (5, 6)
        return {}

    pushed = {}

    def push_fn(kb, colors, *, brightness: int, enable_user_mode: bool):
        pushed["kb"] = kb
        pushed["colors"] = dict(colors)
        pushed["brightness"] = brightness
        pushed["enable_user_mode"] = enable_user_mode
        return kb1

    clear_all_ui(ed, num_rows=5, num_cols=6, clear_fn=clear_fn, push_fn=push_fn)

    assert ed.colors == {}
    assert ed.canvas.redraw_calls == 1
    assert ed.config.effect == "perkey"
    assert ed.config.per_key_colors == {}
    assert ed.kb is kb1
    assert pushed == {
        "kb": kb0,
        "colors": {},
        "brightness": 77,
        "enable_user_mode": True,
    }
    assert ed.status_label.text == "Cleared all keys"
    assert ed.commit_calls == []
