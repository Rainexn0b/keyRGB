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
from typing import Any, Callable

import tkinter as tk
from tkinter import ttk

from ._color_wheel_ui import _ColorWheelUIMixin
from .color_wheel_image import (
    build_wheel_ppm_bytes,
    wheel_cache_path,
    write_bytes_atomic,
)


class ColorWheel(_ColorWheelUIMixin, ttk.Frame):
    """
    A circular color wheel widget for intuitive color selection.
    """

    def __init__(
        self,
        parent,
        size=300,
        initial_color=(255, 0, 0),
        callback: Callable[..., Any] | None = None,
        release_callback: Callable[..., Any] | None = None,
        *,
        show_rgb_label: bool = True,
        brightness_label_text: str = "Brightness:",
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
        # RGB is always on the 0..255 per-channel scale.
        self.callback: Callable[..., Any] | None = callback
        self.release_callback: Callable[..., Any] | None = release_callback
        self.current_color: tuple[int, int, int] = (
            int(initial_color[0]),
            int(initial_color[1]),
            int(initial_color[2]),
        )
        self.show_rgb_label = bool(show_rgb_label)
        self._brightness_label_text = str(brightness_label_text or "Brightness:")

        # Convert RGB to HSV for positioning
        r, g, b = [float(x) / 255.0 for x in self.current_color]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        self.current_hue = h
        self.current_saturation = s
        # Stored as 0..1, but displayed/communicated as percent (0..100).
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
        self.canvas.create_oval(
            x - size,
            y - size,
            x + size,
            y + size,
            outline="white",
            width=3,
            tags="selector",
        )
        self.canvas.create_oval(
            x - size,
            y - size,
            x + size,
            y + size,
            outline="black",
            width=1,
            tags="selector",
        )

    def _on_click(self, event) -> None:
        """Handle mouse click on the color wheel."""
        if not self._wheel_ready:
            return
        self._select_color_at(event.x, event.y)

    def _on_drag(self, event) -> None:
        """Handle mouse drag on the color wheel."""
        if not self._wheel_ready:
            return
        self._select_color_at(event.x, event.y)

    def _on_release(self, event) -> None:
        """Handle mouse release on the color wheel."""
        if not self._wheel_ready:
            return
        if self.release_callback:
            self._invoke_callback(
                self.release_callback,
                *self.current_color,
                source="wheel_release",
                brightness_percent=float(self.current_value * 100.0),
            )

    def _select_color_at(self, x: int, y: int) -> None:
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

        self._update_color(source="wheel")

    def _on_brightness_change(self, value: str | float) -> None:
        """Handle brightness slider change.

        `ttk.Scale` passes the value as a string on many Tk builds.
        The value is interpreted as a percent on the 0..100 UI scale.
        """

        pct = float(value)
        self.current_value = pct / 100.0
        self.brightness_label.config(text=f"{int(pct)}%")
        self._update_color(source="brightness")

        # Also trigger release callback when brightness changes (treat as a commit)
        if self.release_callback:
            self._invoke_callback(
                self.release_callback,
                *self.current_color,
                source="brightness",
                brightness_percent=float(pct),
            )

    @staticmethod
    def _invoke_callback(cb, *args, **kwargs) -> None:
        """Invoke a callback, preserving backwards compatibility.

        Older callbacks in this codebase expect exactly three positional args
        (r, g, b). Newer code may accept optional keyword metadata.
        """

        if cb is None:
            return
        try:
            cb(*args, **kwargs)
        except TypeError:
            cb(*args)

    def _update_color(self, *, source: str = "wheel"):
        """Update the current color based on HSV values."""
        # Convert HSV to RGB
        r, g, b = colorsys.hsv_to_rgb(self.current_hue, self.current_saturation, self.current_value)

        self.current_color = (int(r * 255), int(g * 255), int(b * 255))

        self._update_selection()
        self._update_preview()

        if self.callback:
            self._invoke_callback(
                self.callback,
                *self.current_color,
                source=str(source or "wheel"),
                brightness_percent=float(self.current_value * 100.0),
            )

    def get_color(self) -> tuple[int, int, int]:
        """Get the current selected color as (r, g, b) tuple (0..255 each)."""
        return self.current_color

    def set_color(self, r: int, g: int, b: int) -> None:
        """Set the color programmatically."""
        self.current_color = (int(r), int(g), int(b))

        # Convert to HSV
        r_norm, g_norm, b_norm = float(r) / 255.0, float(g) / 255.0, float(b) / 255.0
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


if __name__ == "__main__":
    # Test the color wheel
    try:
        from src.gui.utils.window_icon import apply_keyrgb_window_icon
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
