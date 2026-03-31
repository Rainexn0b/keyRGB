from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.keyboard_layout_panel as keyboard_layout_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeVar:
    def __init__(self, value: str) -> None:
        self._value = value
        self.set_calls: list[str] = []

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = str(value)
        self.set_calls.append(self._value)


def _install_fake_ttk(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[object]]:
    registry: dict[str, list[object]] = {"frames": [], "labels": [], "comboboxes": []}

    class FakeFrame(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["frames"].append(self)

    class FakeLabel(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeCombobox(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            self.set_calls: list[str] = []
            self.bind_calls: list[tuple[str, object]] = []
            self.bound_callbacks: dict[str, object] = {}
            self._value = ""
            registry["comboboxes"].append(self)

        def set(self, value: str) -> None:
            self._value = str(value)
            self.set_calls.append(self._value)

        def get(self) -> str:
            return self._value

        def bind(self, event: str, callback: object) -> None:
            self.bind_calls.append((event, callback))
            self.bound_callbacks[event] = callback

    monkeypatch.setattr(
        keyboard_layout_panel,
        "ttk",
        SimpleNamespace(Frame=FakeFrame, Label=FakeLabel, Combobox=FakeCombobox),
    )
    return registry


def test_keyboard_layout_panel_init_sets_combobox_label_from_layout_id_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ttk(monkeypatch)
    layout_var = _FakeVar("iso")
    toggles: list[str] = []

    keyboard_layout_panel.KeyboardLayoutPanel(
        object(),
        var_physical_layout=layout_var,
        on_toggle=lambda: toggles.append("toggled"),
    )

    combo = registry["comboboxes"][0]
    labels = [layout.label for layout in keyboard_layout_panel.LAYOUT_CATALOG]

    assert combo.options["textvariable"] is layout_var
    assert combo.options["values"] == labels
    assert combo.options["state"] == "readonly"
    assert combo.set_calls == ["ISO (102/105-key)"]
    assert combo.get() == "ISO (102/105-key)"
    assert combo.bind_calls[0][0] == "<<ComboboxSelected>>"
    assert toggles == []


def test_keyboard_layout_panel_init_falls_back_to_first_label_for_unknown_layout_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ttk(monkeypatch)
    layout_var = _FakeVar("not-a-layout")

    keyboard_layout_panel.KeyboardLayoutPanel(
        object(),
        var_physical_layout=layout_var,
        on_toggle=lambda: None,
    )

    combo = registry["comboboxes"][0]
    first_label = keyboard_layout_panel.LAYOUT_CATALOG[0].label

    assert combo.set_calls == [first_label]
    assert combo.get() == first_label
    assert layout_var.get() == "not-a-layout"
    assert layout_var.set_calls == []


def test_keyboard_layout_panel_builds_expected_label_id_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_ttk(monkeypatch)
    layout_var = _FakeVar("ansi")

    panel = keyboard_layout_panel.KeyboardLayoutPanel(
        object(),
        var_physical_layout=layout_var,
        on_toggle=lambda: None,
    )

    assert panel._label_to_id == {
        layout.label: layout.layout_id for layout in keyboard_layout_panel.LAYOUT_CATALOG
    }
    assert panel._id_to_label == {
        layout.layout_id: layout.label for layout in keyboard_layout_panel.LAYOUT_CATALOG
    }


def test_keyboard_layout_panel_selection_updates_var_to_layout_id_and_calls_on_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ttk(monkeypatch)
    layout_var = _FakeVar("auto")
    toggles: list[str] = []

    keyboard_layout_panel.KeyboardLayoutPanel(
        object(),
        var_physical_layout=layout_var,
        on_toggle=lambda: toggles.append("toggled"),
    )

    combo = registry["comboboxes"][0]
    combo.set("JIS (106/109-key)")

    on_select = combo.bound_callbacks["<<ComboboxSelected>>"]
    on_select()

    assert layout_var.get() == "jis"
    assert layout_var.set_calls == ["jis"]
    assert toggles == ["toggled"]