from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk

from src.core.resources.layouts import LAYOUT_CATALOG


_WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


class KeyboardLayoutPanel:
    """Settings panel for selecting the physical keyboard layout."""

    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_physical_layout: tk.StringVar,
        on_toggle: Callable[[], None],
    ) -> None:
        title = ttk.Label(parent, text="Keyboard layout", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Controls which physical key overlay is shown in the per-key editor and "
                "calibrator. Auto-detect probes your hardware; choose a specific layout "
                "to override."
            ),
            font=("Sans", 9),
            wraplength=340,
            justify="left",
        )
        desc.pack(anchor="w", fill="x", pady=(0, 8))

        def _sync_wrap(_event=None) -> None:
            try:
                width = int(parent.winfo_width())
                if width <= 1:
                    return
                desc.configure(wraplength=max(240, width - 24))
            except _WRAP_SYNC_ERRORS:
                return

        try:
            parent.bind("<Configure>", _sync_wrap)
            parent.after(0, _sync_wrap)
        except _WRAP_SYNC_ERRORS:
            pass

        row = ttk.Frame(parent)
        row.pack(anchor="w", fill="x")
        try:
            row.columnconfigure(1, weight=1)
        except _WRAP_SYNC_ERRORS:
            pass

        ttk.Label(row, text="Layout:", font=("Sans", 9)).grid(row=0, column=0, sticky="w", padx=(0, 8))

        _labels = [ld.label for ld in LAYOUT_CATALOG]
        _ids = [ld.layout_id for ld in LAYOUT_CATALOG]

        self._combo = ttk.Combobox(row, textvariable=var_physical_layout, values=_labels, state="readonly", width=28)
        self._combo.grid(row=0, column=1, sticky="ew")

        # Map label → id and id → label for two-way binding.
        self._label_to_id = {ld.label: ld.layout_id for ld in LAYOUT_CATALOG}
        self._id_to_label = {ld.layout_id: ld.label for ld in LAYOUT_CATALOG}

        # The StringVar stores the layout_id; the combobox shows the label.
        # Override the variable to display labels by swapping on trace.
        self._var = var_physical_layout
        current_id = var_physical_layout.get()
        self._combo.set(self._id_to_label.get(current_id, _labels[0]))

        def _on_select(_e=None) -> None:
            selected_label = self._combo.get()
            lid = self._label_to_id.get(selected_label, "auto")
            self._var.set(lid)
            on_toggle()

        self._combo.bind("<<ComboboxSelected>>", _on_select)
