"""Reusable color wheel widget for selecting RGB colors."""

import colorsys
import os
import tkinter as tk
from tkinter import ttk

from ._color_wheel_ui import ColorWheelCallback, _ColorWheelUIMixin
from ._color_wheel_runtime import load_wheel_photo_image, resolve_theme_bg_hex
from .color_wheel_image import (
    build_wheel_ppm_bytes,
    wheel_cache_path,
    write_bytes_atomic,
)
from .utils import (
    derive_border_hex,
    hex_to_rgb,
    hsv_to_xy,
    invoke_callback,
    xy_to_hsv,
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
        callback: ColorWheelCallback | None = None,
        release_callback: ColorWheelCallback | None = None,
        *,
        show_rgb_label: bool = True,
        brightness_label_text: str = "Brightness:",
        show_brightness_slider: bool = True,
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

        self._theme_bg_hex = self._resolve_theme_bg_hex()
        self._theme_bg_rgb = hex_to_rgb(self._theme_bg_hex)
        self._theme_border_hex = derive_border_hex(self._theme_bg_rgb)

        self.size = size  # type: ignore[assignment]
        self.radius = size // 2
        # RGB is always on the 0..255 per-channel scale.
        self.callback: ColorWheelCallback | None = callback
        self.release_callback: ColorWheelCallback | None = release_callback
        self.current_color: tuple[int, int, int] = (
            int(initial_color[0]),
            int(initial_color[1]),
            int(initial_color[2]),
        )
        self.show_rgb_label = bool(show_rgb_label)
        self._brightness_label_text = str(brightness_label_text or "Brightness:")
        self.show_brightness_slider = bool(show_brightness_slider)

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
        self._suspend_brightness_events = False
        # Defer heavy render work so the window can appear immediately.
        self.after(1, self._render_initial)

    def _render_initial(self) -> None:
        self._draw_wheel()
        self._update_selection()
        self._wheel_ready = True

    def _invoke_callback(
        self,
        cb: ColorWheelCallback | None,
        r: int,
        g: int,
        b: int,
        *,
        source: str | None = None,
        brightness_percent: float | None = None,
    ) -> None:
        if source is None and brightness_percent is None:
            invoke_callback(cb, int(r), int(g), int(b))
        elif source is None:
            invoke_callback(cb, int(r), int(g), int(b), brightness_percent=brightness_percent)
        elif brightness_percent is None:
            invoke_callback(cb, int(r), int(g), int(b), source=source)
        else:
            invoke_callback(
                cb,
                int(r),
                int(g),
                int(b),
                source=source,
                brightness_percent=brightness_percent,
            )

    def _draw_wheel(self):
        """Draw the HSV color wheel as a single cached image."""

        self.canvas.delete("wheel")

        # Keep the background consistent with the rest of the app theme.
        center_size = 20

        # PhotoImage needs to be held on the instance to avoid GC.
        # Prefer loading via a file path: it's more reliable across Tk builds than feeding
        # a large base64 "data" payload (some systems intermittently fail to parse PPM data).
        self._wheel_image = load_wheel_photo_image(
            size=self.size,
            bg_rgb=self._theme_bg_rgb,
            center_size=center_size,
            wheel_cache_path_fn=wheel_cache_path,
            build_wheel_ppm_bytes_fn=build_wheel_ppm_bytes,
            write_bytes_atomic_fn=write_bytes_atomic,
            photo_image_factory=tk.PhotoImage,
            unlink_fn=os.unlink,
        )
        self.canvas.create_image(0, 0, anchor="nw", image=self._wheel_image, tags="wheel")

        # Center outline helps readability (matches older look).
        self.canvas.create_oval(
            self.radius - center_size,
            self.radius - center_size,
            self.radius + center_size,
            self.radius + center_size,
            fill="",
            outline=self._theme_border_hex,
            tags="wheel",
        )

    def _resolve_theme_bg_hex(self) -> str:
        """Best-effort resolve a background color that matches ttk theme."""

        return resolve_theme_bg_hex(
            self,
            style_factory=ttk.Style,
            style_errors=(RuntimeError, tk.TclError),
            widget_bg_errors=(AttributeError, RuntimeError, tk.TclError),
        )

    def _update_selection(self):
        """Update the selection indicator on the wheel."""
        self.canvas.delete("selector")

        # Calculate position based on hue and saturation
        x, y = hsv_to_xy(self.current_hue, self.current_saturation, self.radius)

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
        res = xy_to_hsv(x, y, self.radius)
        if res is None:
            return  # Outside wheel

        h, s = res
        if h is None:
            # Center circle
            self.current_saturation = 0
            # Keep previous hue
        else:
            self.current_hue = h
            self.current_saturation = s

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

        if self._suspend_brightness_events:
            return

        # Also trigger release callback when brightness changes (treat as a commit)
        if self.release_callback:
            self._invoke_callback(
                self.release_callback,
                *self.current_color,
                source="brightness",
                brightness_percent=float(pct),
            )

    def set_brightness_percent(self, pct: float | int) -> None:
        """Set the brightness slider programmatically (0..100) without callbacks."""

        try:
            pct_f = float(pct)
        except (TypeError, ValueError):
            pct_f = 0.0
        pct_f = max(0.0, min(100.0, pct_f))

        try:
            self._suspend_brightness_events = True
            # Setting the variable updates the slider; some Tk builds will call
            # the Scale command, so `_on_brightness_change` must be guarded.
            if hasattr(self, "brightness_var"):
                self.brightness_var.set(pct_f)
            # Ensure internal state and visuals match even if Tk doesn't invoke.
            self.current_value = pct_f / 100.0
            if hasattr(self, "brightness_label"):
                self.brightness_label.config(text=f"{int(pct_f)}%")
            self._update_color(source="brightness")
        finally:
            self._suspend_brightness_events = False

    def _update_color(self, *, source: str = "wheel"):
        """Update the current color based on HSV values."""
        # Convert HSV to RGB
        r, g, b = colorsys.hsv_to_rgb(self.current_hue, self.current_saturation, self.current_value)

        self.current_color = (int(r * 255), int(g * 255), int(b * 255))

        self._update_selection()
        self._update_preview()

        if source == "brightness" and self._suspend_brightness_events:
            return

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

        # Coto HSV
        r_norm, g_norm, b_norm = float(r) / 255.0, float(g) / 255.0, float(b) / 255.0
        h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)

        self.current_hue = h
        self.current_saturation = s
        self.current_value = v

        if hasattr(self, "brightness_var"):
            self.brightness_var.set(v * 100)
        # Keep the percentage label in sync when the slider is updated
        # programmatically (some Tk themes do not call the Scale command).
        if hasattr(self, "brightness_label"):
            self.brightness_label.config(text=f"{int(v * 100)}%")

        self._update_selection()
        self._update_preview()


if __name__ == "__main__":
    from .demo import main

    main()
