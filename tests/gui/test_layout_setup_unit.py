from __future__ import annotations

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
        self._sync_description_wrap = layout_setup.LayoutSetupControls._sync_description_wrap.__get__(self, _FakeSelf)

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

    refresh_calls: list[object] = []
    monkeypatch.setattr(layout_setup, "refresh_layout_slots_ui", lambda editor: refresh_calls.append(editor))

    editor = SimpleNamespace(
        _physical_layout=layout_setup.LAYOUT_CATALOG[0].layout_id,
        _reset_layout_defaults=lambda: None,
    )
    fake_self = _FakeSelf(editor)

    layout_setup.LayoutSetupControls._build_ui(fake_self)

    assert fake_self.columnconfigure_calls == [(1, 1)]
    assert len(combo_instances) == 1
    assert combo_instances[0].kwargs["values"] == layout_setup._LAYOUT_LABELS
    assert combo_instances[0].kwargs["state"] == "readonly"
    assert combo_instances[0].value == layout_setup._ID_TO_LABEL[editor._physical_layout]
    assert combo_instances[0].bind_calls[0][0] == "<<ComboboxSelected>>"
    assert combo_instances[0].bind_calls[0][1] == fake_self._on_layout_select
    assert fake_self.bind_calls == [("<Configure>", fake_self._sync_description_wrap, True)]
    assert fake_self.after_idle_calls == [fake_self._sync_description_wrap]
    assert button_factory.created[0].kwargs["command"] == editor._reset_layout_defaults
    assert editor._layout_combo is combo_instances[0]
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

    editor = SimpleNamespace(_physical_layout="missing", _reset_layout_defaults=lambda: None)
    fake_self = _FakeSelf(editor)

    layout_setup.LayoutSetupControls._build_ui(fake_self)

    assert combo_instances[0].value == layout_setup._LAYOUT_LABELS[0]


def test_sync_description_wrap_updates_wraplength_and_handles_width_errors() -> None:
    label = _FakeWidget()
    fake_self = SimpleNamespace(_description_label=label, winfo_width=lambda: 180)

    layout_setup.LayoutSetupControls._sync_description_wrap(fake_self)
    assert label.configure_calls == [{"wraplength": 200}]

    fake_self_bad = SimpleNamespace(_description_label=label, winfo_width=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
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