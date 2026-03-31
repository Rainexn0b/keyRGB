from __future__ import annotations

from tkinter import ttk
from typing import Any

from src.core.resources.layouts import LAYOUT_CATALOG

from .layout_slots import refresh_layout_slots_ui


_LAYOUT_LABELS = [layout.label for layout in LAYOUT_CATALOG]
_ID_TO_LABEL = {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}
_LABEL_TO_ID = {layout.label: layout.layout_id for layout in LAYOUT_CATALOG}


class LayoutSetupControls(ttk.LabelFrame):
    def __init__(self, parent: ttk.Frame, editor: Any, **kwargs) -> None:
        super().__init__(parent, text="Keyboard setup", padding=10, **kwargs)
        self.editor = editor
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Layout").grid(row=0, column=0, sticky="w")

        self.editor._layout_combo = ttk.Combobox(
            self,
            values=_LAYOUT_LABELS,
            state="readonly",
            width=22,
        )
        current_label = _ID_TO_LABEL.get(self.editor._physical_layout, _LAYOUT_LABELS[0])
        self.editor._layout_combo.set(current_label)
        self.editor._layout_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.editor._layout_combo.bind("<<ComboboxSelected>>", self._on_layout_select)

        self._description_label = ttk.Label(
            self,
            text="Choose the physical layout here when setting up the keyboard or refreshing its saved setup.",
            font=("Sans", 9),
            justify="left",
            anchor="w",
        )
        self._description_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.bind("<Configure>", self._sync_description_wrap, add=True)
        self.after_idle(self._sync_description_wrap)

        ttk.Button(
            self,
            text="Reset Layout Defaults",
            command=self.editor._reset_layout_defaults,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        layout_slots_frame = ttk.LabelFrame(self, text="Optional keys", padding=10)
        layout_slots_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        layout_slots_frame.columnconfigure(0, weight=1)

        self.editor._layout_slots_body = ttk.Frame(layout_slots_frame)
        self.editor._layout_slots_body.grid(row=0, column=0, sticky="ew")
        self.editor._layout_slots_body.columnconfigure(0, weight=1)

        refresh_layout_slots_ui(self.editor)

    def _sync_description_wrap(self, _event=None) -> None:
        try:
            width = int(self.winfo_width())
        except Exception:
            return
        self._description_label.configure(wraplength=max(200, width - 24))

    def _on_layout_select(self, _event=None) -> None:
        selected = self.editor._layout_combo.get()
        self.editor._layout_var.set(_LABEL_TO_ID.get(selected, "auto"))
        self.editor._on_layout_changed()
