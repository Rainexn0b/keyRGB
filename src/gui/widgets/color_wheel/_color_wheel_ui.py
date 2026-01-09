#!/usr/bin/env python3
"""UI helpers for the ColorWheel widget.

This module exists to keep src/gui/widgets/color_wheel.py smaller and easier
to navigate while keeping behavior unchanged.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class _ColorWheelUIMixin:
    def _create_widgets(self):
        """Create the canvas, brightness slider, preview, and manual RGB inputs."""
        bg = getattr(self, "_theme_bg_hex", None) or "#2b2b2b"
        border = getattr(self, "_theme_border_hex", None) or "#666666"
        # Canvas for the color wheel
        self.canvas = tk.Canvas(self, width=self.size, height=self.size, highlightthickness=0, bg=bg)
        self.canvas.pack(pady=10)

        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Brightness/Value slider
        brightness_frame = ttk.Frame(self)
        brightness_frame.pack(fill="x", padx=20, pady=10)

        self.brightness_title_label = ttk.Label(brightness_frame, text=self._brightness_label_text)
        self.brightness_title_label.pack(side="left", padx=(0, 10))

        self.brightness_var = tk.DoubleVar(value=self.current_value * 100)
        self.brightness_slider = ttk.Scale(
            brightness_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.brightness_var,
            command=self._on_brightness_change,
        )
        self.brightness_slider.pack(side="left", fill="x", expand=True)

        self.brightness_label = ttk.Label(brightness_frame, text=f"{int(self.current_value * 100)}%")
        # Prevent label width changes from causing layout/geometry jitter and avoid clipping of the percent sign
        self.brightness_label.configure(width=5)
        self.brightness_label.pack(side="left", padx=(10, 5))

        # Color preview
        preview_frame = ttk.Frame(self)
        preview_frame.pack(fill="x", padx=20, pady=10)

        ttk.Label(preview_frame, text="Selected Color:").pack(side="left", padx=(0, 10))

        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=100,
            height=30,
            highlightthickness=1,
            highlightbackground=border,
            bg=bg,
        )
        # Fixed-size preview to avoid geometry changes during drag
        self.preview_canvas.pack(side="left")

        self.rgb_label = None
        if self.show_rgb_label:
            self.rgb_label = ttk.Label(preview_frame, text="", width=16)
            self.rgb_label.pack(side="left", padx=(10, 0))

        # Manual RGB input (useful for copying exact values).
        manual_frame = ttk.Frame(self)
        manual_frame.pack(fill="x", padx=20, pady=(0, 10))

        ttk.Label(manual_frame, text="RGB:").pack(side="left", padx=(0, 8))

        self._rgb_entry_syncing = False
        self.rgb_r_var = tk.StringVar(value=str(int(self.current_color[0])))
        self.rgb_g_var = tk.StringVar(value=str(int(self.current_color[1])))
        self.rgb_b_var = tk.StringVar(value=str(int(self.current_color[2])))

        self.rgb_r_entry = ttk.Entry(manual_frame, textvariable=self.rgb_r_var, width=4)
        self.rgb_g_entry = ttk.Entry(manual_frame, textvariable=self.rgb_g_var, width=4)
        self.rgb_b_entry = ttk.Entry(manual_frame, textvariable=self.rgb_b_var, width=4)
        self.rgb_r_entry.pack(side="left")
        ttk.Label(manual_frame, text=",").pack(side="left", padx=(2, 2))
        self.rgb_g_entry.pack(side="left")
        ttk.Label(manual_frame, text=",").pack(side="left", padx=(2, 2))
        self.rgb_b_entry.pack(side="left")

        ttk.Button(manual_frame, text="Set", command=self._on_manual_rgb_set).pack(side="left", padx=(10, 0))

        for ent in (self.rgb_r_entry, self.rgb_g_entry, self.rgb_b_entry):
            ent.bind("<Return>", lambda _e: self._on_manual_rgb_set())

        self._update_preview()

    def set_brightness_label_text(self, text: str) -> None:
        """Update the brightness label text (UI clarity).

        This does not change behavior, only the label shown to the user.
        """

        self._brightness_label_text = str(text or "")
        if not self._brightness_label_text:
            self._brightness_label_text = "Brightness:"
        if hasattr(self, "brightness_title_label"):
            try:
                self.brightness_title_label.config(text=self._brightness_label_text)
            except Exception:
                pass

    def _update_preview(self):
        """Update the color preview box."""
        r, g, b = self.current_color
        color_hex = f"#{r:02x}{g:02x}{b:02x}"

        self.preview_canvas.delete("all")
        self.preview_canvas.create_rectangle(0, 0, 200, 30, fill=color_hex, outline="")

        if self.rgb_label is not None:
            # No spaces to keep it compact.
            self.rgb_label.config(text=f"RGB({r},{g},{b})")

        # Keep manual entry fields in sync with the current color.
        if hasattr(self, "_rgb_entry_syncing") and not self._rgb_entry_syncing:
            try:
                self._rgb_entry_syncing = True
                self.rgb_r_var.set(str(int(r)))
                self.rgb_g_var.set(str(int(g)))
                self.rgb_b_var.set(str(int(b)))
            finally:
                self._rgb_entry_syncing = False

    def _on_manual_rgb_set(self) -> None:
        """Apply a manually entered RGB value and fire callbacks."""

        def _parse(v: str) -> int:
            try:
                return int(str(v).strip())
            except Exception:
                return 0

        r = max(0, min(255, _parse(self.rgb_r_var.get())))
        g = max(0, min(255, _parse(self.rgb_g_var.get())))
        b = max(0, min(255, _parse(self.rgb_b_var.get())))

        # Update wheel visuals without triggering external callbacks.
        self.set_color(r, g, b)

        # Manual set should behave like a "commit": notify listeners.
        if self.callback:
            self._invoke_callback(
                self.callback,
                r,
                g,
                b,
                source="manual",
                brightness_percent=float(self.current_value * 100.0),
            )
        if self.release_callback:
            self._invoke_callback(
                self.release_callback,
                r,
                g,
                b,
                source="manual",
                brightness_percent=float(self.current_value * 100.0),
            )
