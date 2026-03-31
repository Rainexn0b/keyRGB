from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from src.core.resources.layout_slots import get_layout_slot_states


def refresh_layout_slots_ui(editor: Any) -> None:
    body = getattr(editor, "_layout_slots_body", None)
    if body is None:
        return

    for child in list(body.winfo_children()):
        child.destroy()

    states = get_layout_slot_states(editor._physical_layout, getattr(editor, "layout_slot_overrides", {}))
    if not states:
        ttk.Label(
            body,
            text="This layout has no optional key positions.",
            font=("Sans", 9),
            wraplength=240,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        return

    ttk.Label(
        body,
        text=(
            "Hide keys your keyboard does not have and rename legends to match the hardware. "
            "These changes are part of the keyboard setup and save immediately for this layout family."
        ),
        font=("Sans", 9),
        wraplength=240,
        justify="left",
    ).grid(row=0, column=0, sticky="w", pady=(0, 8))

    for index, state in enumerate(states, start=1):
        row = ttk.Frame(body)
        row.grid(row=index, column=0, sticky="ew", pady=(0, 4))
        row.columnconfigure(1, weight=1)

        visible_var = tk.BooleanVar(value=state.visible)
        ttk.Checkbutton(
            row,
            text=state.key_id,
            variable=visible_var,
            command=lambda kid=state.key_id, var=visible_var: editor._set_layout_slot_visibility(kid, var.get()),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        label_var = tk.StringVar(value=state.label)
        entry = ttk.Entry(row, textvariable=label_var, width=18)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind(
            "<Return>",
            lambda _e, kid=state.key_id, var=label_var: editor._set_layout_slot_label(kid, var.get()),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e, kid=state.key_id, var=label_var: editor._set_layout_slot_label(kid, var.get()),
        )

        ttk.Label(row, text=f"Default: {state.default_label}", font=("Sans", 8)).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(8, 0),
        )
