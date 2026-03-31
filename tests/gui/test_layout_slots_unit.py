from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import src.gui.perkey.ui.layout_slots as layout_slots


@dataclass(frozen=True)
class _SlotState:
    key_id: str
    visible: bool
    label: str
    default_label: str


class _FakeVar:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.options = dict(kwargs)
        self.children: list[object] = []
        self.grid_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []
        self.destroyed = False
        if parent is not None and hasattr(parent, "children"):
            parent.children.append(self)

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, *, weight: int) -> None:
        self.columnconfigure_calls.append((int(index), int(weight)))

    def winfo_children(self) -> list[object]:
        return list(self.children)

    def destroy(self) -> None:
        self.destroyed = True


def _install_fake_widgets(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[object]]:
    registry: dict[str, list[object]] = {
        "label_frames": [],
        "frames": [],
        "labels": [],
        "checkbuttons": [],
        "entries": [],
    }

    class FakeLabelFrame(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["label_frames"].append(self)

    class FakeFrame(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["frames"].append(self)

    class FakeLabel(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeCheckbutton(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["checkbuttons"].append(self)

    class FakeEntry(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            self.bind_calls: list[tuple[str, object]] = []
            registry["entries"].append(self)

        def bind(self, event: str, callback) -> None:
            self.bind_calls.append((event, callback))

    monkeypatch.setattr(
        layout_slots,
        "ttk",
        SimpleNamespace(
            LabelFrame=FakeLabelFrame,
            Frame=FakeFrame,
            Label=FakeLabel,
            Checkbutton=FakeCheckbutton,
            Entry=FakeEntry,
        ),
    )
    monkeypatch.setattr(layout_slots.tk, "BooleanVar", _FakeVar)
    monkeypatch.setattr(layout_slots.tk, "StringVar", _FakeVar)
    return registry


def _editor() -> SimpleNamespace:
    editor = SimpleNamespace(
        _physical_layout="iso",
        layout_slot_overrides={},
        visibility_calls=[],
        label_calls=[],
    )
    editor._set_layout_slot_visibility = lambda key_id, visible: editor.visibility_calls.append((key_id, visible))
    editor._set_layout_slot_label = lambda key_id, label: editor.label_calls.append((key_id, label))
    return editor


def test_refresh_layout_slots_ui_returns_when_body_missing() -> None:
    editor = _editor()

    layout_slots.refresh_layout_slots_ui(editor)

    assert editor.visibility_calls == []
    assert editor.label_calls == []


def test_refresh_layout_slots_ui_shows_empty_state_and_clears_old_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_widgets(monkeypatch)
    editor = _editor()
    body = _FakeWidget()
    old_child = _FakeWidget(body)
    editor._layout_slots_body = body
    monkeypatch.setattr(layout_slots, "get_layout_slot_states", lambda *_args, **_kwargs: [])

    layout_slots.refresh_layout_slots_ui(editor)

    assert old_child.destroyed is True
    assert registry["labels"][0].options["text"] == "This layout has no optional key positions."
    assert registry["labels"][0].grid_calls == [{"row": 0, "column": 0, "sticky": "w"}]


def test_refresh_layout_slots_ui_builds_rows_and_binds_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_widgets(monkeypatch)
    editor = _editor()
    body = _FakeWidget()
    editor._layout_slots_body = body
    states = [
        _SlotState(key_id="iso_extra", visible=True, label="ISO", default_label="ISO Default"),
    ]
    monkeypatch.setattr(layout_slots, "get_layout_slot_states", lambda *_args, **_kwargs: states)

    layout_slots.refresh_layout_slots_ui(editor)

    assert registry["labels"][0].options["text"].startswith("Hide keys your keyboard does not have")
    checkbutton = registry["checkbuttons"][0]
    entry = registry["entries"][0]
    default_label = registry["labels"][-1]

    assert checkbutton.options["text"] == "iso_extra"
    assert checkbutton.options["variable"].get() is True
    assert default_label.options["text"] == "Default: ISO Default"
    assert [event for event, _ in entry.bind_calls] == ["<Return>", "<FocusOut>"]

    checkbutton.options["variable"].set(False)
    checkbutton.options["command"]()
    assert editor.visibility_calls == [("iso_extra", False)]

    entry.options["textvariable"].set("Renamed")
    for _event, callback in entry.bind_calls:
        callback(None)
    assert editor.label_calls == [("iso_extra", "Renamed"), ("iso_extra", "Renamed")]