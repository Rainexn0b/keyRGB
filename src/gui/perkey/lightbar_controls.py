from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.core.profile import profiles
from src.core.resources.defaults import get_default_lightbar_overlay

from .lightbar_layout import lightbar_rect_for_size, normalize_lightbar_overlay
from .ui.status import reset_lightbar_overlay, saved_lightbar_overlay, set_status

if TYPE_CHECKING:
    from .editor import PerKeyEditor


class LightbarControls(ttk.LabelFrame):
    def __init__(self, parent, editor: PerKeyEditor, **kwargs):
        super().__init__(parent, text="Lightbar", padding=10, **kwargs)
        self.editor = editor

        self.visible_var = tk.BooleanVar()
        self.length_var = tk.DoubleVar()
        self.thickness_var = tk.DoubleVar()
        self.dx_var = tk.DoubleVar()
        self.dy_var = tk.DoubleVar()
        self.inset_var = tk.DoubleVar()

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text="Single-zone placement preview for the auxiliary lightbar",
            font=("Sans", 9),
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        ttk.Checkbutton(self, text="Visible", variable=self.visible_var, command=self.apply_from_vars).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 6),
        )

        self.preview_canvas = tk.Canvas(self, height=88, highlightthickness=1)
        self.preview_canvas.grid(row=2, column=0, sticky="ew")
        self.preview_canvas.bind("<Configure>", lambda _e: self.redraw_preview())

        controls = ttk.Frame(self)
        controls.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(1, weight=1)

        self._add_scale_row(controls, 0, "Length", self.length_var, 0.20, 1.00)
        self._add_scale_row(controls, 1, "Thickness", self.thickness_var, 0.04, 0.40)
        self._add_scale_row(controls, 2, "Offset X", self.dx_var, -0.50, 0.50)
        self._add_scale_row(controls, 3, "Offset Y", self.dy_var, -0.50, 0.50)
        self._add_scale_row(controls, 4, "Inset", self.inset_var, 0.00, 0.25)

        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        ttk.Button(actions, text="Apply", command=self.apply_from_vars).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Save", command=self.save_tweaks).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Reset", command=self.reset_tweaks).grid(row=0, column=2, sticky="ew")

    def _add_scale_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.DoubleVar,
        minimum: float,
        maximum: float,
    ) -> None:
        ttk.Label(parent, text=label, width=10).grid(row=row, column=0, sticky="w")
        ttk.Scale(
            parent,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            variable=variable,
            command=lambda _value: self.apply_from_vars(),
        ).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(0, 6))

    def sync_vars_from_editor(self) -> None:
        payload = dict(getattr(self.editor, "lightbar_overlay", {}) or {})
        defaults = get_default_lightbar_overlay()
        self.visible_var.set(bool(payload.get("visible", defaults["visible"])))
        self.length_var.set(float(payload.get("length", defaults["length"])))
        self.thickness_var.set(float(payload.get("thickness", defaults["thickness"])))
        self.dx_var.set(float(payload.get("dx", defaults["dx"])))
        self.dy_var.set(float(payload.get("dy", defaults["dy"])))
        self.inset_var.set(float(payload.get("inset", defaults["inset"])))
        self.redraw_preview()

    def _redraw_editor_canvas(self) -> None:
        canvas = getattr(self.editor, "canvas", None)
        redraw = getattr(canvas, "redraw", None)
        if not callable(redraw):
            return

        try:
            redraw()
        except (AttributeError, tk.TclError):
            return
        except Exception:  # @quality-exception exception-transparency: per-key lightbar control redraw crosses Tk widget lifetime and canvas implementation callbacks and must remain non-fatal for overlay editing
            return

    def apply_from_vars(self) -> dict[str, bool | float]:
        payload = normalize_lightbar_overlay(
            {
                "visible": bool(self.visible_var.get()),
                "length": self.length_var.get(),
                "thickness": self.thickness_var.get(),
                "dx": self.dx_var.get(),
                "dy": self.dy_var.get(),
                "inset": self.inset_var.get(),
            }
        )
        self.editor.lightbar_overlay = payload
        self.redraw_preview()
        self._redraw_editor_canvas()
        return payload

    def save_tweaks(self) -> None:
        payload = self.apply_from_vars()
        self.editor.lightbar_overlay = profiles.save_lightbar_overlay(payload, self.editor.profile_name)
        set_status(self.editor, saved_lightbar_overlay())

    def reset_tweaks(self) -> None:
        self.editor.lightbar_overlay = get_default_lightbar_overlay()
        self.sync_vars_from_editor()
        self._redraw_editor_canvas()
        set_status(self.editor, reset_lightbar_overlay())

    def redraw_preview(self) -> None:
        canvas = getattr(self, "preview_canvas", None)
        if canvas is None:
            return

        try:
            width = max(120.0, float(canvas.winfo_width()))
            height = max(48.0, float(canvas.winfo_height()))
        except (TypeError, ValueError, tk.TclError):
            width = 180.0
            height = 88.0

        payload = normalize_lightbar_overlay(dict(getattr(self.editor, "lightbar_overlay", {}) or {}))

        canvas.delete("all")
        canvas.create_rectangle(8, 8, width - 8, height - 8, outline="#7f7f7f")

        rect = lightbar_rect_for_size(width=width, height=height, overlay=payload)
        if rect is None:
            return

        x1, y1, x2, y2 = rect

        canvas.create_rectangle(x1, y1, x2, y2, fill="#f28c28", outline="#f7c56f")


__all__ = ["LightbarControls"]
