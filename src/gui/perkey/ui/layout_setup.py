from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Protocol, cast

from src.core.resources.layout_legends import get_layout_legend_pack_ids, load_layout_legend_pack
from src.core.resources.layouts import LAYOUT_CATALOG
from src.gui.widgets.dropdown import UpwardListboxDropdown

from .layout_slots import refresh_layout_slots_ui


class _StringVarProtocol(Protocol):
    def set(self, value: object) -> None: ...


class _ComboboxProtocol(Protocol):
    def set(self, value: object) -> None: ...

    def get(self) -> str: ...

    def grid(self, **kwargs: object) -> None: ...

    def bind(self, event: str, callback: object, add: object | None = None) -> object | None: ...

    def configure(self, **kwargs: object) -> None: ...


class _GridFrameProtocol(Protocol):
    def grid(self, **kwargs: object) -> None: ...

    def columnconfigure(self, index: int, *, weight: int) -> None: ...


class _DropdownProtocol(Protocol):
    def open(self, _event: object = None) -> str: ...


class _LayoutSetupEditorProtocol(Protocol):
    _physical_layout: str
    _layout_legend_pack: str | None
    _layout_var: _StringVarProtocol
    _legend_pack_var: _StringVarProtocol
    _layout_combo: _ComboboxProtocol
    _legend_pack_combo: _ComboboxProtocol
    _layout_dropdown: _DropdownProtocol
    _legend_pack_dropdown: _DropdownProtocol
    _layout_slots_body: _GridFrameProtocol
    _reset_layout_defaults: Callable[[], None]

    def _on_layout_changed(self) -> None: ...

    def _on_layout_legend_pack_changed(self) -> None: ...


_LAYOUT_LABELS = [layout.label for layout in LAYOUT_CATALOG]
_ID_TO_LABEL = {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}
_LABEL_TO_ID = {layout.label: layout.layout_id for layout in LAYOUT_CATALOG}
_AUTO_LEGEND_PACK_ID = "auto"
_AUTO_LEGEND_PACK_LABEL = "Default legends"

_DESCRIPTION_WRAP_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)


def _legend_pack_choices(layout_id: str) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = [(_AUTO_LEGEND_PACK_ID, _AUTO_LEGEND_PACK_LABEL)]
    seen_labels: set[str] = {_AUTO_LEGEND_PACK_LABEL}

    for pack_id in get_layout_legend_pack_ids(layout_id):
        pack = load_layout_legend_pack(pack_id)
        label = str(pack.get("label") or pack_id).strip() or pack_id
        if label in seen_labels:
            label = f"{label} ({pack_id})"
        seen_labels.add(label)
        choices.append((pack_id, label))

    return choices


def _dropdown_root(editor: object, fallback: object) -> tk.Misc:
    return cast(tk.Misc, getattr(editor, "root", None) or fallback)


def _editor_color(editor: object, *, attr: str, default: str) -> str:
    return str(getattr(editor, attr, default) or default)


def _layout_legend_pack_id(editor: object) -> str:
    try:
        pack_id = cast(_LayoutSetupEditorProtocol, editor)._layout_legend_pack
    except AttributeError:
        return _AUTO_LEGEND_PACK_ID

    return str(pack_id or _AUTO_LEGEND_PACK_ID)


class LayoutSetupControls(ttk.LabelFrame):
    def __init__(self, parent: ttk.Frame, editor: object, **kwargs) -> None:
        super().__init__(parent, text="Keyboard setup", padding=10, **kwargs)
        self.editor = cast(_LayoutSetupEditorProtocol, editor)
        self._build_ui()

    def _build_ui(self) -> None:
        editor = self.editor
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Layout").grid(row=0, column=0, sticky="w")

        layout_combo = ttk.Combobox(
            self,
            values=_LAYOUT_LABELS,
            state="readonly",
            width=22,
        )
        editor._layout_combo = layout_combo
        current_label = _ID_TO_LABEL.get(editor._physical_layout, _LAYOUT_LABELS[0])
        layout_combo.set(current_label)
        layout_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        layout_combo.bind("<<ComboboxSelected>>", self._on_layout_select)
        layout_dropdown = UpwardListboxDropdown(
            root=_dropdown_root(editor, layout_combo),
            anchor=cast(tk.Widget, layout_combo),
            values_provider=lambda: list(_LAYOUT_LABELS),
            get_current_value=lambda: str(layout_combo.get() or current_label),
            set_value=self._set_layout_label,
            bg=_editor_color(editor, attr="bg_color", default="#2b2b2b"),
            fg=_editor_color(editor, attr="fg_color", default="#ffffff"),
        )
        editor._layout_dropdown = layout_dropdown
        layout_combo.bind("<Button-1>", layout_dropdown.open)
        layout_combo.bind("<Down>", layout_dropdown.open)

        ttk.Label(self, text="Legends").grid(row=1, column=0, sticky="w", pady=(8, 0))

        legend_pack_combo = ttk.Combobox(
            self,
            state="readonly",
            width=22,
        )
        editor._legend_pack_combo = legend_pack_combo
        legend_pack_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        legend_pack_combo.bind("<<ComboboxSelected>>", self._on_legend_pack_select)
        legend_pack_dropdown = UpwardListboxDropdown(
            root=_dropdown_root(editor, legend_pack_combo),
            anchor=cast(tk.Widget, legend_pack_combo),
            values_provider=lambda: [label for _pack_id, label in _legend_pack_choices(editor._physical_layout)],
            get_current_value=lambda: str(legend_pack_combo.get() or _AUTO_LEGEND_PACK_LABEL),
            set_value=self._set_legend_pack_label,
            bg=_editor_color(editor, attr="bg_color", default="#2b2b2b"),
            fg=_editor_color(editor, attr="fg_color", default="#ffffff"),
        )
        editor._legend_pack_dropdown = legend_pack_dropdown
        legend_pack_combo.bind("<Button-1>", legend_pack_dropdown.open)
        legend_pack_combo.bind("<Down>", legend_pack_dropdown.open)
        self.refresh_legend_pack_choices()

        self._description_label = ttk.Label(
            self,
            text="Choose the physical layout here when setting up the keyboard or refreshing its saved setup.",
            font=("Sans", 9),
            justify="left",
            anchor="w",
        )
        self._description_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.bind("<Configure>", self._sync_description_wrap, add=True)
        self.after_idle(self._sync_description_wrap)

        ttk.Button(
            self,
            text="Reset Layout Defaults",
            command=editor._reset_layout_defaults,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        layout_slots_frame = ttk.LabelFrame(self, text="Optional keys", padding=10)
        layout_slots_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        layout_slots_frame.columnconfigure(0, weight=1)

        layout_slots_body = ttk.Frame(layout_slots_frame)
        editor._layout_slots_body = layout_slots_body
        layout_slots_body.grid(row=0, column=0, sticky="ew")
        layout_slots_body.columnconfigure(0, weight=1)

        refresh_layout_slots_ui(editor)

    def refresh_legend_pack_choices(self) -> None:
        editor = self.editor
        choices = _legend_pack_choices(editor._physical_layout)
        id_to_label = {pack_id: label for pack_id, label in choices}
        label_to_id = {label: pack_id for pack_id, label in choices}
        self._legend_pack_id_to_label = id_to_label
        self._legend_pack_label_to_id = label_to_id

        current_pack_id = _layout_legend_pack_id(editor)
        current_label = id_to_label.get(current_pack_id, _AUTO_LEGEND_PACK_LABEL)

        editor._legend_pack_combo.configure(values=[label for _pack_id, label in choices])
        editor._legend_pack_combo.set(current_label)

    def _sync_description_wrap(self, _event=None) -> None:
        try:
            width = int(self.winfo_width())
        except _DESCRIPTION_WRAP_ERRORS:
            return
        self._description_label.configure(wraplength=max(200, width - 24))

    def _set_layout_label(self, label: str) -> None:
        editor = self.editor
        editor._layout_combo.set(str(label))
        self._on_layout_select()

    def _set_legend_pack_label(self, label: str) -> None:
        editor = self.editor
        editor._legend_pack_combo.set(str(label))
        self._on_legend_pack_select()

    def _on_layout_select(self, _event=None) -> None:
        editor = self.editor
        selected = editor._layout_combo.get()
        editor._layout_var.set(_LABEL_TO_ID.get(selected, "auto"))
        editor._on_layout_changed()

    def _on_legend_pack_select(self, _event=None) -> None:
        editor = self.editor
        selected = editor._legend_pack_combo.get()
        editor._legend_pack_var.set(self._legend_pack_label_to_id.get(selected, _AUTO_LEGEND_PACK_ID))
        editor._on_layout_legend_pack_changed()
