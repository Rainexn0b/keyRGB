#!/usr/bin/env python3
"""
Uniform Color GUI - Simple color wheel for selecting a single keyboard color.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

try:
    from .color_wheel import ColorWheel
    from .config_legacy import Config
except Exception:
    # Fallback for direct execution (e.g. `python src/gui_uniform.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.color_wheel import ColorWheel
    from src.config_legacy import Config

try:
    from ite8291r3_ctl.ite8291r3 import get
except Exception:
    # Repo fallback if dependency wasn't installed.
    repo_root = Path(__file__).resolve().parent.parent
    vendored = repo_root / "ite8291r3-ctl"
    if vendored.exists():
        sys.path.insert(0, str(vendored))
    from ite8291r3_ctl.ite8291r3 import get


class UniformColorGUI:
    """Simple GUI for selecting a uniform keyboard color."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('KeyRGB - Uniform Color')
        self.root.geometry('450x550')
        self.root.resizable(False, False)
        
        # Dark theme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        bg_color = '#2b2b2b'
        fg_color = '#e0e0e0'
        
        self.root.configure(bg=bg_color)
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TButton', background='#404040', foreground=fg_color)
        style.map('TButton',
                  background=[('active', '#505050')])
        
        # Initialize config (tray app will apply changes if it's running)
        self.config = Config()

        # Try to acquire device for standalone mode; if tray app owns it, we'll defer.
        self.kb = None
        try:
            self.kb = get()
        except Exception:
            # Likely "resource busy" because the tray app already owns the USB device.
            self.kb = None
        
        # Main container
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        title = ttk.Label(
            main_frame,
            text='Select Uniform Keyboard Color',
            font=('Sans', 14, 'bold')
        )
        title.pack(pady=(0, 10))
        
        # Color wheel
        self.color_wheel = ColorWheel(
            main_frame,
            size=350,
            initial_color=tuple(self.config.color) if isinstance(self.config.color, list) else self.config.color,
            callback=self._on_color_change,
            release_callback=self._on_color_release
        )
        self.color_wheel.pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill='x')
        
        apply_btn = ttk.Button(
            button_frame,
            text='Apply',
            command=self._on_apply
        )
        apply_btn.pack(side='left', padx=(0, 10), fill='x', expand=True)
        
        close_btn = ttk.Button(
            button_frame,
            text='Close',
            command=self._on_close
        )
        close_btn.pack(side='left', fill='x', expand=True)
        
        # Status label
        self.status_label = ttk.Label(
            main_frame,
            text='',
            font=('Sans', 9)
        )
        self.status_label.pack()
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f'+{x}+{y}')

        self._pending_color = None
        self._last_drag_commit_ts = 0.0
        self._last_drag_committed_color = None

        # Throttle config writes while dragging (seconds)
        self._drag_commit_interval = 0.06
        
    def _on_color_change(self, r, g, b):
        """Handle color wheel changes (during drag)."""
        # Apply in real-time while dragging by writing config.
        # The tray app owns the hardware device, so it will pick up config changes.
        color = (r, g, b)
        self._pending_color = color

        now = time.monotonic()
        if self._last_drag_committed_color == color and (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        if (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        # Ensure we're in static mode so animations don't overwrite the chosen color.
        if self.config.effect != 'none':
            self.config.effect = 'none'

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
            if getattr(e, "errno", None) == 16:
                self.kb = None
                return "deferred"
            print(f"Error setting color: {e}")
            return False
        except Exception as e:
            print(f"Error setting color: {e}")
            return False
    
    def _on_color_release(self, r, g, b):
        """Handle color wheel release (apply and save)."""
        # Get current brightness, use config value or default to 25 if it's 0
        brightness = self.config.brightness
        if brightness == 0:
            brightness = 25
            self.config.brightness = brightness  # Auto-saves
        
        # Stop any running effects first, then save the color (auto-saves)
        self.config.effect = 'none'
        self.config.color = (r, g, b)

        self._last_drag_committed_color = (r, g, b)
        self._last_drag_commit_ts = time.monotonic()

        # Apply to keyboard (or defer to tray app if it's running)
        result = self._apply_color(r, g, b, brightness)
        if result is True:
            msg = f'✓ Applied RGB({r}, {g}, {b})'
            color = '#00ff00'
        elif result == "deferred":
            msg = f'✓ Saved RGB({r}, {g}, {b})'
            color = '#00ff00'
        else:
            msg = '✗ Error applying color'
            color = '#ff0000'

        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=''))
        
    def _on_apply(self):
        """Apply the selected color to the keyboard."""
        r, g, b = self.color_wheel.get_color()
        
        # Get current brightness, use config value or default to 25 if it's 0
        brightness = self.config.brightness
        if brightness == 0:
            brightness = 25
            self.config.brightness = brightness  # Auto-saves
        
        # Stop any running effects first, then save the color (auto-saves)
        self.config.effect = 'none'
        self.config.color = (r, g, b)

        # Apply to keyboard (or defer to tray app if it's running)
        result = self._apply_color(r, g, b, brightness)
        if result is True:
            msg = f'✓ Applied RGB({r}, {g}, {b})'
            color = '#00ff00'
        elif result == "deferred":
            msg = f'✓ Saved RGB({r}, {g}, {b})'
            color = '#00ff00'
        else:
            msg = '✗ Error applying color'
            color = '#ff0000'

        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=''))
            
    def _on_close(self):
        """Close the window."""
        self.root.destroy()
        
    def run(self):
        """Start the GUI."""
        self.root.mainloop()


def main():
    app = UniformColorGUI()
    app.run()


if __name__ == '__main__':
    main()
