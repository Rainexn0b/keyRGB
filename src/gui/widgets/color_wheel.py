#!/usr/bin/env python3
"""Simple color wheel widget for selecting RGB colors.

Reusable component for both uniform and per-key color selection.

Performance note:
The original implementation drew tens of thousands of tiny polygons on a Canvas.
That is very slow on many systems (especially in power-saver modes). This widget
now renders the wheel as a single image (cached on disk), and draws only the
selector overlay on top.
"""

import base64
import colorsys
import math

import tkinter as tk
from tkinter import ttk

from .color_wheel_image import build_wheel_ppm_bytes, wheel_cache_path, write_bytes_atomic


class ColorWheel(ttk.Frame):
    """
    A circular color wheel widget for intuitive color selection.
    """

    def __init__(
        self,
        parent,
        size=300,
        initial_color=(255, 0, 0),
        callback=None,
        release_callback=None,
        *,
        show_rgb_label: bool = True,
    ):
        """
        Initialize the color wheel.

        Args:
            parent: Parent widget
            size: Diameter of the color wheel in pixels
            initial_color: Initial RGB color tuple (r, g, b) where values are 0-255
            callback: Function to call when color changes, receives (r, g, b) tuple
            release_callback: Function to call when mouse is released, receives (r, g, b) tuple
        """
        super().__init__(parent)

        self.size = size
        self.radius = size // 2
        self.callback = callback
        self.release_callback = release_callback
        self.current_color = initial_color
        self.show_rgb_label = bool(show_rgb_label)

        # Convert RGB to HSV for positioning
        r, g, b = [x / 255.0 for x in initial_color]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        self.current_hue = h
        self.current_saturation = s
        self.current_value = v

        self._create_widgets()
        self._wheel_image: tk.PhotoImage | None = None
        self._wheel_ready = False
        # Defer heavy render work so the window can appear immediately.
        self.after(1, self._render_initial)

    def _render_initial(self) -> None:
        self._draw_wheel()
        self._update_selection()
        self._wheel_ready = True

    def _create_widgets(self):
        """Create the canvas and brightness slider."""
        # Canvas for the color wheel
        self.canvas = tk.Canvas(self, width=self.size, height=self.size, highlightthickness=0, bg="#2b2b2b")
        self.canvas.pack(pady=10)

        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Brightness/Value slider
        brightness_frame = ttk.Frame(self)
        brightness_frame.pack(fill="x", padx=20, pady=10)

        ttk.Label(brightness_frame, text="Brightness:").pack(side="left", padx=(0, 10))

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
        # Prevent label width changes from causing layout/geometry jitter
        self.brightness_label.configure(width=4)
        self.brightness_label.pack(side="left", padx=(10, 0))

        # Color preview
        preview_frame = ttk.Frame(self)
        preview_frame.pack(fill="x", padx=20, pady=10)

        ttk.Label(preview_frame, text="Selected Color:").pack(side="left", padx=(0, 10))

        self.preview_canvas = tk.Canvas(
            preview_frame, width=100, height=30, highlightthickness=1, highlightbackground="#666666"
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

    def _draw_wheel(self):
        """Draw the HSV color wheel as a single cached image."""

        self.canvas.delete("wheel")

        # Keep the background consistent with the rest of the app theme.
        bg_rgb = (0x2B, 0x2B, 0x2B)
        center_size = 20

        wheel_path = wheel_cache_path(size=self.size)
        ppm_bytes: bytes | None = None

        try:
            if not wheel_path.exists() or wheel_path.stat().st_size < 16:
                wheel_path.parent.mkdir(parents=True, exist_ok=True)
                ppm_bytes = build_wheel_ppm_bytes(size=self.size, bg_rgb=bg_rgb, center_size=center_size)
                write_bytes_atomic(wheel_path, ppm_bytes)
        except Exception:
            # Cache path may be unwritable (restricted envs, sandboxing, etc).
            ppm_bytes = build_wheel_ppm_bytes(size=self.size, bg_rgb=bg_rgb, center_size=center_size)

        # PhotoImage needs to be held on the instance to avoid GC.
        if ppm_bytes is not None:
            # Tk's PhotoImage `data` expects a base64-encoded string.
            self._wheel_image = tk.PhotoImage(data=base64.b64encode(ppm_bytes).decode("ascii"), format="PPM")
        else:
            self._wheel_image = tk.PhotoImage(file=str(wheel_path))
        self.canvas.create_image(0, 0, anchor="nw", image=self._wheel_image, tags="wheel")

        # Center outline helps readability (matches older look).
        self.canvas.create_oval(
            self.radius - center_size,
            self.radius - center_size,
            self.radius + center_size,
            self.radius + center_size,
            fill="",
            outline="#888888",
            tags="wheel",
        )

    def _update_selection(self):
        """Update the selection indicator on the wheel."""
        self.canvas.delete("selector")

        # Calculate position based on hue and saturation
        angle = self.current_hue * 2 * math.pi
        distance = self.current_saturation * (self.radius - 20)  # -20 for center circle

        x = self.radius + distance * math.cos(angle)
        y = self.radius + distance * math.sin(angle)

        # Draw selection circle
        size = 8
        self.canvas.create_oval(x - size, y - size, x + size, y + size, outline="white", width=3, tags="selector")
        self.canvas.create_oval(x - size, y - size, x + size, y + size, outline="black", width=1, tags="selector")

    def _on_click(self, event):
        """Handle mouse click on the color wheel."""
        if not self._wheel_ready:
            return
        self._select_color_at(event.x, event.y)

    def _on_drag(self, event):
        """Handle mouse drag on the color wheel."""
        if not self._wheel_ready:
            return
        self._select_color_at(event.x, event.y)

    def _on_release(self, event):
        """Handle mouse release on the color wheel."""
        if not self._wheel_ready:
            return
        if self.release_callback:
            self.release_callback(*self.current_color)

    def _select_color_at(self, x, y):
        """Select color at the given canvas coordinates."""
        # Calculate distance and angle from center
        dx = x - self.radius
        dy = y - self.radius
        distance = math.sqrt(dx * dx + dy * dy)

        # Clamp to wheel radius (minus center circle)
        max_distance = self.radius - 20
        if distance > self.radius:
            return  # Outside wheel

        if distance < 20:
            # In center circle - keep current hue but set saturation to 0
            self.current_saturation = 0
        else:
            # Calculate hue and saturation
            angle = math.atan2(dy, dx)
            if angle < 0:
                angle += 2 * math.pi

            self.current_hue = angle / (2 * math.pi)
            self.current_saturation = min(distance / max_distance, 1.0)

        self._update_color()

    def _on_brightness_change(self, value):
        """Handle brightness slider change."""
        self.current_value = float(value) / 100.0
        self.brightness_label.config(text=f"{int(float(value))}%")
        self._update_color()

        # Also trigger release callback when brightness changes
        if self.release_callback:
            self.release_callback(*self.current_color)

    def _update_color(self):
        """Update the current color based on HSV values."""
        # Convert HSV to RGB
        r, g, b = colorsys.hsv_to_rgb(self.current_hue, self.current_saturation, self.current_value)

        self.current_color = (int(r * 255), int(g * 255), int(b * 255))

        self._update_selection()
        self._update_preview()

        if self.callback:
            self.callback(*self.current_color)

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

    def get_color(self):
        """Get the current selected color as (r, g, b) tuple."""
        return self.current_color

    def set_color(self, r, g, b):
        """Set the color programmatically."""
        self.current_color = (r, g, b)

        # Convert to HSV
        r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)

        self.current_hue = h
        self.current_saturation = s
        self.current_value = v

        self.brightness_var.set(v * 100)
        # Keep the percentage label in sync when the slider is updated
        # programmatically (some Tk themes do not call the Scale command).
        if hasattr(self, "brightness_label"):
            self.brightness_label.config(text=f"{int(v * 100)}%")

        self._update_selection()
        self._update_preview()

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
            self.callback(r, g, b)
        if self.release_callback:
            self.release_callback(r, g, b)


if __name__ == "__main__":
    # Test the color wheel
    try:
        from src.gui.window_icon import apply_keyrgb_window_icon
    except Exception:
        apply_keyrgb_window_icon = None

    root = tk.Tk()
    root.title("Color Wheel Test")
    if apply_keyrgb_window_icon is not None:
        apply_keyrgb_window_icon(root)
    root.geometry("400x500")

    def on_color_change(r, g, b):
        print(f"Color changed to RGB({r}, {g}, {b})")

    wheel = ColorWheel(root, size=350, initial_color=(255, 0, 0), callback=on_color_change)
    wheel.pack(padx=20, pady=20)

    root.mainloop()
