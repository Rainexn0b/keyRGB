from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .editor import PerKeyEditor

class OverlayControls(ttk.LabelFrame):
    def __init__(self, parent, editor: PerKeyEditor, **kwargs):
        super().__init__(parent, text="Overlay alignment", padding=10, **kwargs)
        self.editor = editor
        
        self.dx_var = tk.DoubleVar()
        self.dy_var = tk.DoubleVar()
        self.sx_var = tk.DoubleVar()
        self.sy_var = tk.DoubleVar()
        self.inset_var = tk.DoubleVar()
        
        self._build_ui()

    def _build_ui(self):
        scope_row = ttk.Frame(self)
        scope_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Radiobutton(scope_row, text="Global", variable=self.editor.overlay_scope, value="global", command=self.sync_vars_from_scope).pack(side="left")
        ttk.Radiobutton(scope_row, text="Selected key", variable=self.editor.overlay_scope, value="key", command=self.sync_vars_from_scope).pack(side="left", padx=(10, 0))

        def add_row(row: int, label: str, var: tk.DoubleVar):
            ttk.Label(self, text=label, width=6).grid(row=row, column=0, sticky="w")
            e = ttk.Entry(self, textvariable=var, width=10)
            e.grid(row=row, column=1, sticky="ew", padx=(6, 0))
            e.bind("<Return>", lambda _e: self.apply_from_vars())
            e.bind("<FocusOut>", lambda _e: self.apply_from_vars())

        self.columnconfigure(1, weight=1)
        add_row(1, "dx", self.dx_var)
        add_row(2, "dy", self.dy_var)
        add_row(3, "sx", self.sx_var)
        add_row(4, "sy", self.sy_var)
        add_row(5, "inset", self.inset_var)

        overlay_btns = ttk.Frame(self)
        overlay_btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        overlay_btns.columnconfigure(0, weight=1)
        overlay_btns.columnconfigure(1, weight=1)
        overlay_btns.columnconfigure(2, weight=1)

        ttk.Button(overlay_btns, text="Apply", command=self.apply_from_vars).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(overlay_btns, text="Save", command=self.save_tweaks).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(overlay_btns, text="Reset", command=self.reset_tweaks).grid(row=0, column=2, sticky="ew")

        ttk.Button(self, text="Auto Sync", command=self.auto_sync).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def sync_vars_from_scope(self):
        if self.editor.overlay_scope.get() == "key" and self.editor.selected_key_id:
            kt = self.editor.per_key_layout_tweaks.get(self.editor.selected_key_id, {})
            self.dx_var.set(float(kt.get("dx", 0.0)))
            self.dy_var.set(float(kt.get("dy", 0.0)))
            self.sx_var.set(float(kt.get("sx", 1.0)))
            self.sy_var.set(float(kt.get("sy", 1.0)))
            self.inset_var.set(float(kt.get("inset", float(self.editor.layout_tweaks.get("inset", 0.06)))))
            return

        self.dx_var.set(float(self.editor.layout_tweaks.get("dx", 0.0)))
        self.dy_var.set(float(self.editor.layout_tweaks.get("dy", 0.0)))
        self.sx_var.set(float(self.editor.layout_tweaks.get("sx", 1.0)))
        self.sy_var.set(float(self.editor.layout_tweaks.get("sy", 1.0)))
        self.inset_var.set(float(self.editor.layout_tweaks.get("inset", 0.06)))

    def apply_from_vars(self):
        def f(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, float(v)))

        payload = {
            "dx": float(self.dx_var.get()),
            "dy": float(self.dy_var.get()),
            "sx": f(self.sx_var.get(), 0.3, 4.0),
            "sy": f(self.sy_var.get(), 0.3, 4.0),
            "inset": f(self.inset_var.get(), 0.0, 80.0),
        }

        if self.editor.overlay_scope.get() == "key" and self.editor.selected_key_id:
            self.editor.per_key_layout_tweaks[self.editor.selected_key_id] = payload
        else:
            self.editor.layout_tweaks = payload
        self.editor.canvas.redraw()

    def save_tweaks(self):
        self.apply_from_vars()
        self.editor.save_layout_tweaks()

    def reset_tweaks(self):
        self.editor.reset_layout_tweaks()

    def auto_sync(self):
        self.editor.auto_sync_per_key_overlays()
