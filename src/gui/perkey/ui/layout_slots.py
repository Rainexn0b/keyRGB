from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from src.core.resources.layout_slots import get_layout_slot_states


def _body_wraplength(body: Any, *, fallback: int = 520) -> int:
    try:
        width = int(body.winfo_width())
    except Exception:
        return fallback
    return max(320, width - 12)


def refresh_layout_slots_ui(editor: Any) -> None:
    body = getattr(editor, "_layout_slots_body", None)
    if body is None:
        return

    for child in list(body.winfo_children()):
        child.destroy()

    slot_states_getter = getattr(editor, "_get_layout_slot_states", None)
    if callable(slot_states_getter):
        states = slot_states_getter()
    else:
        states = get_layout_slot_states(editor._physical_layout, getattr(editor, "layout_slot_overrides", {}))
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
        slot_id = getattr(state, "slot_id", state.key_id)
        row = ttk.Frame(body)
        row.grid(row=index, column=0, sticky="ew", pady=(0, 4))
        row.columnconfigure(1, weight=1)

        visible_var = tk.BooleanVar(value=state.visible)
        ttk.Checkbutton(
            row,
            text=state.key_id,
            variable=visible_var,
            command=lambda slot_id=slot_id, var=visible_var: editor._set_layout_slot_visibility(slot_id, var.get()),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        label_var = tk.StringVar(value=state.label)
        entry = ttk.Entry(row, textvariable=label_var, width=18)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind(
            "<Return>",
            lambda _e, slot_id=slot_id, var=label_var: editor._set_layout_slot_label(slot_id, var.get()),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e, slot_id=slot_id, var=label_var: editor._set_layout_slot_label(slot_id, var.get()),
        )

        ttk.Label(row, text=f"Default: {state.default_label}", font=("Sans", 8)).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(8, 0),
        )
