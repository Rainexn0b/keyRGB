from __future__ import annotations

from dataclasses import dataclass

from src.gui.perkey.ui.sample_tool import on_key_clicked_ui, on_sample_tool_toggled_ui, on_slot_clicked_ui


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = str(text)


class DummyBool:
    def __init__(self, v: bool):
        self.v = bool(v)

    def get(self) -> bool:
        return bool(self.v)

    def set(self, v: bool) -> None:
        self.v = bool(v)


class DummyCanvas:
    def __init__(self):
        self.redraw_calls = 0

    def redraw(self) -> None:
        self.redraw_calls += 1


class DummyWheel:
    def __init__(self):
        self._color = (0, 0, 0)
        self.set_calls: list[tuple[int, int, int]] = []

    def set_color(self, r: int, g: int, b: int) -> None:
        self._color = (int(r), int(g), int(b))
        self.set_calls.append(self._color)

    def get_color(self):
        return self._color


@dataclass
class DummyEditor:
    keymap: dict
    colors: dict

    selected_key_id: str | None
    selected_cells: tuple[tuple[int, int], ...]
    selected_cell: tuple[int, int] | None

    sample_tool_enabled: DummyBool
    _sample_tool_has_sampled: bool

    status_label: DummyLabel
    canvas: DummyCanvas
    color_wheel: DummyWheel

    select_calls: list[str]
    select_slot_calls: list[str]
    apply_calls: list[tuple[int, int, int, int, int]]
    selected_slot_id: str | None = None

    def select_key_id(self, key_id: str) -> None:
        self.select_calls.append(str(key_id))

    def select_slot_id(self, slot_id: str) -> None:
        self.select_slot_calls.append(str(slot_id))

    def _slot_id_for_key_id(self, key_id: str) -> str | None:
        if str(key_id) == "K1":
            return "slot_k1"
        if str(key_id) == "A":
            return "slot_a"
        if str(key_id) == "B":
            return "slot_b"
        return None

    def _key_id_for_slot_id(self, slot_id: str) -> str | None:
        if str(slot_id) == "slot_k1":
            return "K1"
        if str(slot_id) == "slot_a":
            return "A"
        if str(slot_id) == "slot_b":
            return "B"
        return None


def test_toggle_sample_tool_sets_instruction_and_resets_state() -> None:
    ed = DummyEditor(
        keymap={},
        colors={},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(True),
        _sample_tool_has_sampled=True,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    on_sample_tool_toggled_ui(ed)

    assert ed._sample_tool_has_sampled is False
    assert "click" in ed.status_label.text.lower()


def test_sample_tool_first_click_samples_color_into_wheel() -> None:
    ed = DummyEditor(
        keymap={"K1": ((0, 0), (0, 1))},
        colors={(0, 0): (12, 34, 56)},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(True),
        _sample_tool_has_sampled=False,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    def apply_release_fn(*_args, **_kwargs):
        raise AssertionError("should not apply on first click")

    on_key_clicked_ui(ed, "K1", num_rows=6, num_cols=21, apply_release_fn=apply_release_fn)

    assert ed._sample_tool_has_sampled is True
    assert ed.selected_cells == ((0, 0), (0, 1))
    assert ed.color_wheel.get_color() == (12, 34, 56)
    assert "sampled" in ed.status_label.text.lower()


def test_sample_tool_second_click_applies_current_wheel_color() -> None:
    ed = DummyEditor(
        keymap={"A": ((0, 0),), "B": ((0, 1), (0, 2))},
        colors={(0, 0): (1, 2, 3), (0, 1): (9, 9, 9)},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(True),
        _sample_tool_has_sampled=True,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    ed.color_wheel.set_color(7, 8, 9)

    def apply_release_fn(editor, r: int, g: int, b: int, *, num_rows: int, num_cols: int):
        editor.apply_calls.append((r, g, b, int(num_rows), int(num_cols)))

    on_key_clicked_ui(ed, "B", num_rows=6, num_cols=21, apply_release_fn=apply_release_fn)

    assert ed.apply_calls == [(7, 8, 9, 6, 21)]


def test_sample_tool_off_delegates_to_select() -> None:
    ed = DummyEditor(
        keymap={"K1": ((0, 0),)},
        colors={(0, 0): (12, 34, 56)},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(False),
        _sample_tool_has_sampled=True,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    on_key_clicked_ui(ed, "K1", num_rows=6, num_cols=21)

    assert ed._sample_tool_has_sampled is False
    assert ed.select_calls == []
    assert ed.select_slot_calls == ["slot_k1"]


def test_slot_click_off_delegates_to_slot_selection() -> None:
    ed = DummyEditor(
        keymap={"K1": ((0, 0),)},
        colors={(0, 0): (12, 34, 56)},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(False),
        _sample_tool_has_sampled=True,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    on_slot_clicked_ui(ed, "slot_k1", num_rows=6, num_cols=21)

    assert ed._sample_tool_has_sampled is False
    assert ed.select_calls == []
    assert ed.select_slot_calls == ["slot_k1"]


def test_slot_click_in_sample_mode_uses_resolved_key_identity() -> None:
    ed = DummyEditor(
        keymap={"K1": ((0, 0), (0, 1))},
        colors={(0, 0): (12, 34, 56)},
        selected_key_id=None,
        selected_cells=(),
        selected_cell=None,
        sample_tool_enabled=DummyBool(True),
        _sample_tool_has_sampled=False,
        status_label=DummyLabel(),
        canvas=DummyCanvas(),
        color_wheel=DummyWheel(),
        select_calls=[],
        select_slot_calls=[],
        apply_calls=[],
    )

    on_slot_clicked_ui(ed, "slot_k1", num_rows=6, num_cols=21)

    assert ed._sample_tool_has_sampled is True
    assert ed.selected_key_id == "K1"
    assert ed.selected_slot_id == "slot_k1"
    assert ed.selected_cells == ((0, 0), (0, 1))
    assert ed.color_wheel.get_color() == (12, 34, 56)
