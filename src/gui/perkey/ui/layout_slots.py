from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Protocol, Sequence, cast

from src.core.resources.layout_slots import get_layout_slot_states

LayoutSlotOverrides = dict[str, dict[str, object]]


class _DestroyableWidgetProtocol(Protocol):
    def destroy(self) -> None: ...


class _LayoutSlotsBodyProtocol(Protocol):
    def winfo_children(self) -> Sequence[_DestroyableWidgetProtocol]: ...

    def winfo_width(self) -> int: ...


class _LayoutSlotStateProtocol(Protocol):
    key_id: str
    visible: bool
    label: str
    default_label: str


class _LayoutSlotIdentityOwner(Protocol):
    slot_id: str


class _BooleanVarProtocol(Protocol):
    def get(self) -> bool: ...


class _StringVarProtocol(Protocol):
    def get(self) -> str: ...


class _LayoutSlotsBodyOwner(Protocol):
    _layout_slots_body: _LayoutSlotsBodyProtocol


class _LayoutSlotStatesGetterProtocol(Protocol):
    def __call__(self) -> Sequence[_LayoutSlotStateProtocol]: ...


class _LayoutSlotStatesGetterOwner(Protocol):
    _get_layout_slot_states: _LayoutSlotStatesGetterProtocol


class _LayoutSlotOverridesOwner(Protocol):
    layout_slot_overrides: LayoutSlotOverrides


class _LayoutSlotVisibilitySetterProtocol(Protocol):
    def _set_layout_slot_visibility(self, slot_id: str, visible: bool) -> None: ...


class _LayoutSlotLabelSetterProtocol(Protocol):
    def _set_layout_slot_label(self, slot_id: str, label: str) -> None: ...


class _PhysicalLayoutOwner(Protocol):
    _physical_layout: str


class _LayoutSlotsEditorProtocol(
    _PhysicalLayoutOwner,
    _LayoutSlotVisibilitySetterProtocol,
    _LayoutSlotLabelSetterProtocol,
    Protocol,
):
    pass


def _body_wraplength(body: _LayoutSlotsBodyProtocol, *, fallback: int = 520) -> int:
    try:
        width = int(body.winfo_width())
    except tk.TclError:
        return fallback
    return max(320, width - 12)


def _layout_slots_body_or_none(editor: object) -> _LayoutSlotsBodyProtocol | None:
    try:
        return cast(_LayoutSlotsBodyOwner, editor)._layout_slots_body
    except AttributeError:
        return None


def _layout_slot_states_getter_or_none(editor: object) -> _LayoutSlotStatesGetterProtocol | None:
    try:
        return cast(_LayoutSlotStatesGetterOwner, editor)._get_layout_slot_states
    except AttributeError:
        return None


def _layout_slot_overrides_or_empty(editor: object) -> LayoutSlotOverrides:
    try:
        return cast(_LayoutSlotOverridesOwner, editor).layout_slot_overrides
    except AttributeError:
        return {}


def _layout_slot_id(state: _LayoutSlotStateProtocol) -> str:
    try:
        return cast(_LayoutSlotIdentityOwner, state).slot_id
    except AttributeError:
        return state.key_id


def _layout_slot_visibility_callback(
    editor: _LayoutSlotsEditorProtocol, *, slot_id: str, var: _BooleanVarProtocol
) -> Callable[[], None]:
    def _apply() -> None:
        editor._set_layout_slot_visibility(slot_id, var.get())

    return _apply


def _layout_slot_label_callback(
    editor: _LayoutSlotsEditorProtocol, *, slot_id: str, var: _StringVarProtocol
) -> Callable[[object], None]:
    def _apply(_event: object) -> None:
        editor._set_layout_slot_label(slot_id, var.get())

    return _apply


def refresh_layout_slots_ui(editor: object) -> None:
    body = _layout_slots_body_or_none(editor)
    if body is None:
        return

    for child in list(body.winfo_children()):
        child.destroy()

    typed_editor = cast(_LayoutSlotsEditorProtocol, editor)
    slot_states_getter = _layout_slot_states_getter_or_none(editor)
    if slot_states_getter is not None and callable(slot_states_getter):
        states = slot_states_getter()
    else:
        states = get_layout_slot_states(
            typed_editor._physical_layout,
            _layout_slot_overrides_or_empty(editor),
        )
    if not states:
        ttk.Label(
            body,
            text="This layout has no optional key positions.",
            font=("Sans", 9),
            wraplength=_body_wraplength(body),
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        return

    for index, state in enumerate(states):
        slot_id = _layout_slot_id(state)
        row = ttk.Frame(body)
        row.grid(row=index, column=0, sticky="ew", pady=(0, 4))
        row.columnconfigure(1, weight=1)

        visible_var = cast(_BooleanVarProtocol, tk.BooleanVar(value=state.visible))
        ttk.Checkbutton(
            row,
            text=state.key_id,
            variable=visible_var,
            command=_layout_slot_visibility_callback(typed_editor, slot_id=slot_id, var=visible_var),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        label_var = cast(_StringVarProtocol, tk.StringVar(value=state.label))
        entry = ttk.Entry(row, textvariable=label_var, width=18)
        entry.grid(row=0, column=1, sticky="ew")
        commit_label = _layout_slot_label_callback(typed_editor, slot_id=slot_id, var=label_var)
        entry.bind("<Return>", commit_label)
        entry.bind("<FocusOut>", commit_label)

        ttk.Label(row, text=f"Default: {state.default_label}", font=("Sans", 8)).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(8, 0),
        )
