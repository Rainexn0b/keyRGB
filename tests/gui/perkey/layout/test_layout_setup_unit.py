from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest

from src.gui.perkey.ui import layout_setup


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.grid_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []
        self.bind_calls: list[tuple[str, object, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.set_value = None

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(kwargs)

    def columnconfigure(self, index: int, *, weight: int) -> None:
        self.columnconfigure_calls.append((index, weight))

    def bind(self, event: str, callback, add=None) -> None:
        self.bind_calls.append((event, callback, add))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(kwargs)

    def set(self, value) -> None:
        self.set_value = value


class _FakeCombobox(_FakeWidget):
    def __init__(self, parent=None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.value = ""

    def set(self, value) -> None:
        self.value = value

    def get(self):
        return self.value


class _FakeDropdown:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def open(self, _event=None):
        return "break"


class _FakeFactory:
    def __init__(self) -> None:
        self.created: list[_FakeWidget] = []

    def __call__(self, parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        self.created.append(widget)
        return widget


class _FakeFrameFactory:
    def __init__(self) -> None:
        self.created: list[_FakeWidget] = []

    def __call__(self, parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        self.created.append(widget)
        return widget


class _FakeSelf:
    def __init__(self, editor) -> None:
        self.editor = editor
        self.columnconfigure_calls: list[tuple[int, int]] = []
        self.bind_calls: list[tuple[str, object, object]] = []
        self.after_idle_calls: list[object] = []
        self._description_label = None
        self.width = 320
        self._on_layout_select = layout_setup.LayoutSetupControls._on_layout_select.__get__(self, _FakeSelf)
        self._on_legend_pack_select = layout_setup.LayoutSetupControls._on_legend_pack_select.__get__(self, _FakeSelf)
        self._set_layout_label = layout_setup.LayoutSetupControls._set_layout_label.__get__(self, _FakeSelf)
        self._set_legend_pack_label = layout_setup.LayoutSetupControls._set_legend_pack_label.__get__(self, _FakeSelf)
        self._sync_description_wrap = layout_setup.LayoutSetupControls._sync_description_wrap.__get__(self, _FakeSelf)
        self.refresh_legend_pack_choices = layout_setup.LayoutSetupControls.refresh_legend_pack_choices.__get__(
            self, _FakeSelf
        )

    def columnconfigure(self, index: int, *, weight: int) -> None:
        self.columnconfigure_calls.append((index, weight))

    def bind(self, event: str, callback, add=None) -> None:
        self.bind_calls.append((event, callback, add))

    def after_idle(self, callback) -> None:
        self.after_idle_calls.append(callback)

    def winfo_width(self) -> int:
        return self.width


def test_build_ui_creates_layout_controls_and_refreshes_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    label_factory = _FakeFactory()
    frame_factory = _FakeFrameFactory()
    button_factory = _FakeFactory()
    combo_instances: list[_FakeCombobox] = []
    dropdown_instances: list[_FakeDropdown] = []

    def make_combo(parent=None, **kwargs):
        widget = _FakeCombobox(parent, **kwargs)
        combo_instances.append(widget)
        return widget

    monkeypatch.setattr(
        layout_setup,
        "ttk",
        SimpleNamespace(
            Label=label_factory,
            Combobox=make_combo,
            Button=button_factory,
            LabelFrame=frame_factory,
            Frame=frame_factory,
        ),
    )
    monkeypatch.setattr(
        layout_setup,
        "UpwardListboxDropdown",
        lambda **kwargs: dropdown_instances.append(_FakeDropdown(**kwargs)) or dropdown_instances[-1],
    )

    refresh_calls: list[object] = []
    monkeypatch.setattr(layout_setup, "refresh_layout_slots_ui", lambda editor: refresh_calls.append(editor))

    editor = SimpleNamespace(
        _physical_layout=layout_setup.LAYOUT_CATALOG[0].layout_id,
        _layout_legend_pack="auto",
        _legend_pack_var=SimpleNamespace(set=lambda value: None),
        _on_layout_legend_pack_changed=lambda: None,
        _reset_layout_defaults=lambda: None,
    )
    fake_self = _FakeSelf(editor)

    monkeypatch.setattr(
        layout_setup,
        "_legend_pack_choices",
        lambda _layout_id: [("auto", "Default legends"), ("ansi-generic", "ANSI Generic")],
    )

    layout_setup.LayoutSetupControls._build_ui(fake_self)

    assert fake_self.columnconfigure_calls == [(1, 1)]
    assert len(combo_instances) == 2
    assert combo_instances[0].kwargs["values"] == layout_setup._LAYOUT_LABELS
    assert combo_instances[0].kwargs["state"] == "readonly"
    assert combo_instances[0].value == layout_setup._ID_TO_LABEL[editor._physical_layout]
    assert [call[0] for call in combo_instances[0].bind_calls] == ["<<ComboboxSelected>>", "<Button-1>", "<Down>"]
    assert combo_instances[0].bind_calls[0][1] == fake_self._on_layout_select
    assert combo_instances[1].kwargs["state"] == "readonly"
    assert combo_instances[1].configure_calls == [{"values": ["Default legends", "ANSI Generic"]}]
    assert combo_instances[1].value == "Default legends"
    assert [call[0] for call in combo_instances[1].bind_calls] == ["<<ComboboxSelected>>", "<Button-1>", "<Down>"]
    assert fake_self.bind_calls == [("<Configure>", fake_self._sync_description_wrap, True)]
    assert fake_self.after_idle_calls == [fake_self._sync_description_wrap]
    assert button_factory.created[0].kwargs["command"] == editor._reset_layout_defaults
    assert editor._layout_combo is combo_instances[0]
    assert editor._legend_pack_combo is combo_instances[1]
    assert editor._layout_dropdown is dropdown_instances[0]
    assert editor._legend_pack_dropdown is dropdown_instances[1]
    assert dropdown_instances[0].kwargs["anchor"] is combo_instances[0]
    assert dropdown_instances[0].kwargs["root"] is combo_instances[0]
    assert dropdown_instances[0].kwargs["values_provider"]() == layout_setup._LAYOUT_LABELS
    assert dropdown_instances[0].kwargs["get_current_value"]() == layout_setup._ID_TO_LABEL[editor._physical_layout]
    assert dropdown_instances[1].kwargs["anchor"] is combo_instances[1]
    assert dropdown_instances[1].kwargs["root"] is combo_instances[1]
    assert dropdown_instances[1].kwargs["values_provider"]() == ["Default legends", "ANSI Generic"]
    assert dropdown_instances[1].kwargs["get_current_value"]() == "Default legends"
    assert editor._layout_slots_body is frame_factory.created[-1]
    assert editor._layout_slots_body.columnconfigure_calls == [(0, 1)]
    assert refresh_calls == [editor]


def test_build_ui_falls_back_to_first_layout_label(monkeypatch: pytest.MonkeyPatch) -> None:
    combo_instances: list[_FakeCombobox] = []

    def make_combo(parent=None, **kwargs):
        widget = _FakeCombobox(parent, **kwargs)
        combo_instances.append(widget)
        return widget

    monkeypatch.setattr(
        layout_setup,
        "ttk",
        SimpleNamespace(
            Label=lambda *args, **kwargs: _FakeWidget(*args, **kwargs),
            Combobox=make_combo,
            Button=lambda *args, **kwargs: _FakeWidget(*args, **kwargs),
            LabelFrame=lambda *args, **kwargs: _FakeWidget(*args, **kwargs),
            Frame=lambda *args, **kwargs: _FakeWidget(*args, **kwargs),
        ),
    )
    monkeypatch.setattr(layout_setup, "refresh_layout_slots_ui", lambda editor: None)
    monkeypatch.setattr(layout_setup, "_legend_pack_choices", lambda _layout_id: [("auto", "Default legends")])

    editor = SimpleNamespace(
        _physical_layout="missing",
        _layout_legend_pack="auto",
        _legend_pack_var=SimpleNamespace(set=lambda value: None),
        _on_layout_legend_pack_changed=lambda: None,
        _reset_layout_defaults=lambda: None,
    )
    fake_self = _FakeSelf(editor)

    layout_setup.LayoutSetupControls._build_ui(fake_self)

    assert combo_instances[0].value == layout_setup._LAYOUT_LABELS[0]


def test_sync_description_wrap_updates_wraplength() -> None:
    fake_self = _FakeSelf(SimpleNamespace())
    fake_self._description_label = _FakeWidget()
    fake_self.width = 320

    layout_setup.LayoutSetupControls._sync_description_wrap(fake_self)

    assert fake_self._description_label.configure_calls == [{"wraplength": 296}]


def test_sync_description_wrap_swallows_expected_geometry_errors() -> None:
    class _BrokenSelf(_FakeSelf):
        def winfo_width(self) -> int:
            raise RuntimeError("not mapped yet")

    fake_self = _BrokenSelf(SimpleNamespace())
    fake_self._description_label = _FakeWidget()

    layout_setup.LayoutSetupControls._sync_description_wrap(fake_self)

    assert fake_self._description_label.configure_calls == []


def test_sync_description_wrap_propagates_unexpected_errors() -> None:
    class _BrokenSelf(_FakeSelf):
        def winfo_width(self) -> int:
            raise AssertionError("boom")

    fake_self = _BrokenSelf(SimpleNamespace())
    fake_self._description_label = _FakeWidget()

    with pytest.raises(AssertionError):
        layout_setup.LayoutSetupControls._sync_description_wrap(fake_self)


def test_sync_description_wrap_updates_wraplength_and_handles_width_errors() -> None:
    label = _FakeWidget()
    fake_self = SimpleNamespace(_description_label=label, winfo_width=lambda: 180)

    layout_setup.LayoutSetupControls._sync_description_wrap(fake_self)
    assert label.configure_calls == [{"wraplength": 200}]

    fake_self_bad = SimpleNamespace(
        _description_label=label, winfo_width=lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    layout_setup.LayoutSetupControls._sync_description_wrap(fake_self_bad)
    assert label.configure_calls == [{"wraplength": 200}]


def test_on_layout_select_updates_layout_var_and_notifies_editor() -> None:
    set_calls: list[str] = []
    changed_calls: list[str] = []
    fake_combo = SimpleNamespace(get=lambda: layout_setup._LAYOUT_LABELS[0])
    fake_self = SimpleNamespace(
        editor=SimpleNamespace(
            _layout_combo=fake_combo,
            _layout_var=SimpleNamespace(set=lambda value: set_calls.append(value)),
            _on_layout_changed=lambda: changed_calls.append("changed"),
        )
    )

    layout_setup.LayoutSetupControls._on_layout_select(fake_self)
    assert set_calls == [layout_setup._LABEL_TO_ID[layout_setup._LAYOUT_LABELS[0]]]
    assert changed_calls == ["changed"]

    set_calls.clear()
    fake_self.editor._layout_combo = SimpleNamespace(get=lambda: "Unknown")
    layout_setup.LayoutSetupControls._on_layout_select(fake_self)
    assert set_calls == ["auto"]


def test_set_layout_label_updates_combo_and_notifies_editor() -> None:
    set_calls: list[str] = []
    changed_calls: list[str] = []
    combo = _FakeCombobox()
    fake_self = SimpleNamespace(
        editor=SimpleNamespace(
            _layout_combo=combo,
            _layout_var=SimpleNamespace(set=lambda value: set_calls.append(value)),
            _on_layout_changed=lambda: changed_calls.append("changed"),
        )
    )
    fake_self._on_layout_select = layout_setup.LayoutSetupControls._on_layout_select.__get__(fake_self, SimpleNamespace)

    layout_setup.LayoutSetupControls._set_layout_label(fake_self, "ANSI (101/104-key)")

    assert combo.value == "ANSI (101/104-key)"
    assert set_calls == ["ansi"]
    assert changed_calls == ["changed"]


def test_refresh_legend_pack_choices_updates_combo_from_editor_state() -> None:
    combo = _FakeCombobox()
    editor = SimpleNamespace(_physical_layout="iso", _layout_legend_pack="iso-de-qwertz", _legend_pack_combo=combo)
    fake_self = SimpleNamespace(editor=editor)

    layout_setup.LayoutSetupControls.refresh_legend_pack_choices(fake_self)

    assert combo.configure_calls == [{"values": ["Default legends", "ISO Generic", "ISO German QWERTZ"]}]
    assert combo.value == "ISO German QWERTZ"
    assert fake_self._legend_pack_id_to_label["iso-de-qwertz"] == "ISO German QWERTZ"


def test_on_legend_pack_select_updates_var_and_notifies_editor() -> None:
    set_calls: list[str] = []
    changed_calls: list[str] = []
    fake_self = SimpleNamespace(
        _legend_pack_label_to_id={"ISO German QWERTZ": "iso-de-qwertz"},
        editor=SimpleNamespace(
            _legend_pack_combo=SimpleNamespace(get=lambda: "ISO German QWERTZ"),
            _legend_pack_var=SimpleNamespace(set=lambda value: set_calls.append(value)),
            _on_layout_legend_pack_changed=lambda: changed_calls.append("changed"),
        ),
    )

    layout_setup.LayoutSetupControls._on_legend_pack_select(fake_self)
    assert set_calls == ["iso-de-qwertz"]
    assert changed_calls == ["changed"]


def test_set_legend_pack_label_updates_combo_and_notifies_editor() -> None:
    set_calls: list[str] = []
    changed_calls: list[str] = []
    combo = _FakeCombobox()
    fake_self = SimpleNamespace(
        _legend_pack_label_to_id={"ISO German QWERTZ": "iso-de-qwertz"},
        editor=SimpleNamespace(
            _legend_pack_combo=combo,
            _legend_pack_var=SimpleNamespace(set=lambda value: set_calls.append(value)),
            _on_layout_legend_pack_changed=lambda: changed_calls.append("changed"),
        ),
    )
    fake_self._on_legend_pack_select = layout_setup.LayoutSetupControls._on_legend_pack_select.__get__(
        fake_self, SimpleNamespace
    )

    layout_setup.LayoutSetupControls._set_legend_pack_label(fake_self, "ISO German QWERTZ")

    assert combo.value == "ISO German QWERTZ"
    assert set_calls == ["iso-de-qwertz"]
    assert changed_calls == ["changed"]
