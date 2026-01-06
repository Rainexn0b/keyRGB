#!/usr/bin/env python3
"""Uniform Color GUI - Simple color wheel for selecting a single keyboard color."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from src.core.backends.registry import select_backend
from src.core.runtime.imports import ensure_repo_root_on_sys_path
from src.core.utils.exceptions import is_device_busy
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.utils.window_centering import center_window_on_screen
from src.gui.theme import apply_clam_theme


logger = logging.getLogger(__name__)

try:
    from src.gui.widgets.color_wheel import ColorWheel
    from src.core.config import Config
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/uniform.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.gui.widgets.color_wheel import ColorWheel
    from src.core.config import Config


class UniformColorGUI:
    """Simple GUI for selecting a uniform keyboard color."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Uniform Color")
        apply_keyrgb_window_icon(self.root)
        self.root.geometry("520x610")
        self.root.minsize(520, 610)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        # Initialize config (tray app will apply changes if it's running)
        self.config = Config()

        # Try to acquire device for standalone mode; if tray app owns it, we'll defer.
        self.kb = None
        try:
            backend = select_backend()
            self.kb = backend.get_device() if backend is not None else None
        except Exception:
            # Likely "resource busy" because the tray app already owns the USB device.
            self.kb = None

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill="both", expand=True)

        title = ttk.Label(main_frame, text="Select Uniform Keyboard Color", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        self.color_wheel = ColorWheel(
            main_frame,
            size=350,
            initial_color=(tuple(self.config.color) if isinstance(self.config.color, list) else self.config.color),
            callback=self._on_color_change,
            release_callback=self._on_color_release,
        )
        self.color_wheel.pack()

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill="x")

        apply_btn = ttk.Button(button_frame, text="Apply", command=self._on_apply)
        apply_btn.pack(side="left", padx=(0, 10), fill="x", expand=True)

        close_btn = ttk.Button(button_frame, text="Close", command=self._on_close)
        close_btn.pack(side="left", fill="x", expand=True)

        self.status_label = ttk.Label(main_frame, text="", font=("Sans", 9))
        self.status_label.pack()

        center_window_on_screen(self.root)

        self._pending_color = None
        self._last_drag_commit_ts = 0.0
        self._last_drag_committed_color = None

        # Throttle config writes while dragging (seconds)
        self._drag_commit_interval = 0.06

    def _set_status(self, msg: str, *, ok: bool) -> None:
        color = "#00ff00" if ok else "#ff0000"
        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=""))

    def _ensure_brightness_nonzero(self) -> int:
        brightness = int(self.config.brightness)
        if brightness == 0:
            brightness = 25
            self.config.brightness = brightness  # Auto-saves
        return brightness

    def _commit_color_to_config(self, r: int, g: int, b: int) -> None:
        # Stop any running effects first, then save the color (auto-saves)
        self.config.effect = "none"
        self.config.color = (r, g, b)

    def _on_color_change(self, r, g, b):
        """Handle color wheel changes (during drag)."""
        color = (r, g, b)
        self._pending_color = color

        now = time.monotonic()
        if self._last_drag_committed_color == color and (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return
        if (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        if self.config.effect != "none":
            self.config.effect = "none"

        self.config.color = color
        self._last_drag_commit_ts = now
        self._last_drag_committed_color = color

    def _apply_color(self, r, g, b, brightness):
        """Apply color directly if we own the device; otherwise defer to tray."""
        if self.kb is None:
            return "deferred"

        try:
            self.kb.set_color((r, g, b), brightness=brightness)
            return True
        except OSError as e:
            # Device owned by another process (tray)
            if is_device_busy(e):
                self.kb = None
                return "deferred"
            if os.environ.get("KEYRGB_DEBUG"):
                logger.exception("Error setting color")
            else:
                logger.error("Error setting color: %s", e)
            return False
        except Exception as e:
            if os.environ.get("KEYRGB_DEBUG"):
                logger.exception("Error setting color")
            else:
                logger.error("Error setting color: %s", e)
            return False

    def _on_color_release(self, r, g, b):
        """Handle color wheel release (apply and save)."""
        brightness = self._ensure_brightness_nonzero()
        self._commit_color_to_config(r, g, b)

        self._last_drag_committed_color = (r, g, b)
        self._last_drag_commit_ts = time.monotonic()

        result = self._apply_color(r, g, b, brightness)
        if result is True:
            self._set_status(f"✓ Applied RGB({r}, {g}, {b})", ok=True)
        elif result == "deferred":
            self._set_status(f"✓ Saved RGB({r}, {g}, {b})", ok=True)
        else:
            self._set_status("✗ Error applying color", ok=False)

    def _on_apply(self):
        """Apply the selected color to the keyboard."""
        r, g, b = self.color_wheel.get_color()

        brightness = self._ensure_brightness_nonzero()
        self._commit_color_to_config(r, g, b)

        result = self._apply_color(r, g, b, brightness)
        if result is True:
            self._set_status(f"✓ Applied RGB({r}, {g}, {b})", ok=True)
        elif result == "deferred":
            self._set_status(f"✓ Saved RGB({r}, {g}, {b})", ok=True)
        else:
            self._set_status("✗ Error applying color", ok=False)

    def _on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main() -> None:
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    UniformColorGUI().run()


if __name__ == "__main__":
    main()
