#!/usr/bin/env python3
"""Reactive Typing Color GUI.

Allows selecting a manual highlight color used by reactive typing effects
(`reactive_fade`, `reactive_ripple`) without stopping the currently running
effect.

The tray process (when running) will pick up changes from config polling.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import ttk

from src.core.runtime.imports import ensure_repo_root_on_sys_path
from src.gui.utils.window_centering import center_window_on_screen
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme

logger = logging.getLogger(__name__)

try:
    from src.core.config import Config
    from src.gui.widgets.color_wheel import ColorWheel
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/reactive_color.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.core.config import Config
    from src.gui.widgets.color_wheel import ColorWheel


class ReactiveColorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Reactive Typing Color")
        apply_keyrgb_window_icon(self.root)
        # This window includes extra explanatory text + a toggle above the shared
        # ColorWheel widget; keep it tall enough to avoid clipping.
        desired_w, desired_h = 629, 847
        max_w = int(self.root.winfo_screenwidth() * 0.95)
        max_h = int(self.root.winfo_screenheight() * 0.95)
        w = min(desired_w, max_w)
        h = min(desired_h, max_h)
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(w, h)
        self.root.resizable(True, True)

        apply_clam_theme(self.root, include_checkbuttons=True, map_checkbutton_state=True)

        self.config = Config()

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Reactive Typing Highlight Color", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        desc = ttk.Label(
            main,
            text=(
                "Sets a manual highlight color used by Reactive Typing effects.\n"
                "This does not stop the current effect; the tray will pick up changes automatically.\n"
                "The slider below controls Reactive Typing brightness (pulse/highlight intensity) and is independent from the manual color override."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=max(200, w - 48),
        )
        desc.pack(pady=(0, 10), fill="x")

        def _sync_desc_wrap(_event=None) -> None:
            try:
                ww = int(main.winfo_width())
                if ww > 1:
                    desc.configure(wraplength=max(200, ww - 8))
            except Exception:
                pass

        main.bind("<Configure>", _sync_desc_wrap)
        self.root.after(0, _sync_desc_wrap)

        self._use_manual_var = tk.BooleanVar(value=bool(getattr(self.config, "reactive_use_manual_color", False)))
        ttk.Checkbutton(
            main,
            text="Use manual color for reactive typing",
            variable=self._use_manual_var,
            command=self._on_toggle_manual,
        ).pack(anchor="w", pady=(0, 10))

        initial = self.config.reactive_color
        self.color_wheel = ColorWheel(
            main,
            size=350,
            initial_color=tuple(initial),
            callback=self._on_color_change,
            release_callback=self._on_color_release,
            show_brightness_slider=False,
        )
        self.color_wheel.pack()

        # Divider + independent reactive brightness slider.
        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(18, 12))

        self._reactive_brightness_var = tk.DoubleVar(value=100.0)
        brightness_frame = ttk.Frame(main)
        brightness_frame.pack(fill="x", padx=10)

        ttk.Label(brightness_frame, text="Reactive typing brightness:").pack(side="left", padx=(0, 10))

        self._reactive_brightness_scale = ttk.Scale(
            brightness_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self._reactive_brightness_var,
            command=self._on_reactive_brightness_change,
        )
        self._reactive_brightness_scale.pack(side="left", fill="x", expand=True)

        self._reactive_brightness_label = ttk.Label(brightness_frame, text="100%")
        self._reactive_brightness_label.configure(width=5)
        self._reactive_brightness_label.pack(side="left", padx=(10, 5))

        # Commit on mouse release as well.
        try:
            self._reactive_brightness_scale.bind("<ButtonRelease-1>", self._on_reactive_brightness_release)
        except Exception:
            pass

        # Initialize slider from persisted reactive brightness (0..50 -> 0..100%).
        try:
            hw = int(getattr(self.config, "reactive_brightness", getattr(self.config, "brightness", 0)) or 0)
            pct = max(0, min(100, int(round(hw * 2))))
            self._reactive_brightness_var.set(float(pct))
            self._reactive_brightness_label.config(text=f"{pct}%")
        except Exception:
            pass

        # Initialize the brightness slider from the persisted reactive brightness
        # when manual mode is disabled. Otherwise (manual mode enabled), the
        # slider reflects the manual color brightness.
        try:
            if not bool(self._use_manual_var.get()):
                hw = int(getattr(self.config, "reactive_brightness", getattr(self.config, "brightness", 0)) or 0)
                pct = max(0, min(100, int(round(hw * 2))))
                self.color_wheel.set_brightness_percent(pct)
        except Exception:
            pass

        # Lightweight feedback for manual RGB entry / release.
        self.status_label = ttk.Label(main, text="", font=("Sans", 9))
        self.status_label.pack(pady=(10, 0))

        center_window_on_screen(self.root)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        _orig_report_callback_exception = self.root.report_callback_exception

        def _report_callback_exception(exc, val, tb):
            if isinstance(val, KeyboardInterrupt):
                self._on_close()
                return
            _orig_report_callback_exception(exc, val, tb)

        self.root.report_callback_exception = _report_callback_exception  # type: ignore[assignment]

        # When launched from a terminal, Ctrl+C sends SIGINT to the whole process group.
        # Use a handler to close cleanly without printing a traceback.
        signal.signal(signal.SIGINT, lambda *_: self._on_close())

        self._last_drag_commit_ts = 0.0
        self._last_drag_committed_color: tuple[int, int, int] | None = None
        self._drag_commit_interval = 0.06

        self._last_drag_committed_brightness: int | None = None

    def _set_status(self, msg: str, *, ok: bool) -> None:
        color = "#00ff00" if ok else "#ff0000"
        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=""))

    def _commit_color_to_config(self, color: tuple[int, int, int]) -> None:
        try:
            # Selecting a manual color implies enabling manual mode.
            self.config.reactive_use_manual_color = True
            self._use_manual_var.set(True)
            self.config.reactive_color = color
        except Exception as exc:
            logger.debug("Failed to save reactive_color", exc_info=exc)

    def _commit_brightness_to_config(self, brightness_percent: float | int | None) -> int | None:
        """Persist reactive typing brightness (pulse/highlight intensity)."""
        if brightness_percent is None:
            return None
        try:
            pct = float(brightness_percent)
        except Exception:
            return None

        pct = max(0.0, min(100.0, pct))
        # Config stores brightness on the 0..50 hardware scale.
        hw = int(round(pct / 2.0))
        try:
            self.config.reactive_brightness = hw
        except Exception as exc:
            logger.debug("Failed to save brightness", exc_info=exc)
            return None
        return hw

    def _on_toggle_manual(self) -> None:
        try:
            self.config.reactive_use_manual_color = bool(self._use_manual_var.get())
        except Exception as exc:
            logger.debug("Failed to save reactive_use_manual_color", exc_info=exc)

    def _on_reactive_brightness_change(self, value: str | float) -> None:
        """Handle reactive brightness slider changes (0..100 UI scale)."""

        try:
            pct = float(value)
        except Exception:
            pct = 0.0
        pct = max(0.0, min(100.0, pct))

        try:
            self._reactive_brightness_label.config(text=f"{int(pct)}%")
        except Exception:
            pass

        now = time.monotonic()
        if (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        hw = self._commit_brightness_to_config(pct)
        if hw is not None:
            self._last_drag_commit_ts = now
            self._last_drag_committed_brightness = int(round(hw * 2))

    def _on_reactive_brightness_release(self, _event=None) -> None:
        try:
            pct = float(self._reactive_brightness_var.get())
        except Exception:
            pct = 0.0
        pct = max(0.0, min(100.0, pct))

        hw = self._commit_brightness_to_config(pct)
        if hw is None:
            self._set_status("✗ Failed to save reactive brightness", ok=False)
            return

        pct_i = int(round(hw * 2))
        self._last_drag_commit_ts = time.monotonic()
        self._last_drag_committed_brightness = pct_i
        self._set_status(f"✓ Saved reactive brightness {pct_i}%", ok=True)

    def _on_color_change(self, r: int, g: int, b: int, **meta: Any) -> None:
        color = (int(r), int(g), int(b))
        source = str(meta.get("source") or "")

        now = time.monotonic()
        if self._last_drag_committed_color == color and (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return
        if (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        self._commit_color_to_config(color)
        self._last_drag_commit_ts = now
        self._last_drag_committed_color = color

    def _on_color_release(self, r: int, g: int, b: int, **meta: Any) -> None:
        color = (int(r), int(g), int(b))
        source = str(meta.get("source") or "")

        self._commit_color_to_config(color)
        self._last_drag_committed_color = color
        self._last_drag_commit_ts = time.monotonic()
        self._set_status(f"✓ Saved RGB({color[0]}, {color[1]}, {color[2]})", ok=True)

    def _on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main() -> None:
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    try:
        ReactiveColorGUI().run()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
