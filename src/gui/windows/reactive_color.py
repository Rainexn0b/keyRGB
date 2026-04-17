"""Reactive Typing color picker GUI for live manual-color updates via config polling."""

from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from src.core.runtime.imports import ensure_repo_root_on_sys_path

logger = logging.getLogger(__name__)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_WRAP_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)


try:
    from src.gui.windows import _reactive_color_runtime as _runtime
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/reactive_color.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.gui.windows import _reactive_color_runtime as _runtime


Config = _runtime.Config
select_backend = _runtime.select_backend
ColorWheel = _runtime.ColorWheel
apply_clam_theme = _runtime.apply_clam_theme
apply_keyrgb_window_icon = _runtime.apply_keyrgb_window_icon
compute_centered_window_geometry = _runtime.compute_centered_window_geometry
reactive_color_bootstrap = _runtime.reactive_color_bootstrap
reactive_color_interactions = _runtime.reactive_color_interactions
reactive_color_ui = _runtime.reactive_color_ui


class ReactiveColorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Reactive Typing Settings")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(520, 720)
        self.root.resizable(True, True)

        apply_clam_theme(self.root, include_checkbuttons=True, map_checkbutton_state=True)

        self.config = Config()
        self._last_drag_commit_ts = 0.0
        self._last_drag_committed_color: tuple[int, int, int] | None = None
        self._drag_commit_interval = 0.06
        self._last_drag_committed_brightness: int | None = None

        self._color_supported = reactive_color_bootstrap.probe_color_support(
            select_backend_fn=select_backend,
            logger=logger,
        )

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)
        self._main_frame = main
        self._wrap_labels: list[object] = []

        title = ttk.Label(main, text="Reactive Typing Settings", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        reactive_color_bootstrap.build_description_section(
            self,
            main,
            ttk_module=ttk,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
        )

        reactive_color_ui.build_reactive_window_ui(
            self,
            main,
            tk_module=tk,
            ttk_module=ttk,
            color_wheel_cls=ColorWheel,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
            tk_error=tk.TclError,
        )

        self._apply_geometry()
        self.root.after(50, self._apply_geometry)

        reactive_color_bootstrap.install_lifecycle_bindings(
            self,
            signal_module=signal,
            sigint=signal.SIGINT,
        )

    def _apply_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            geometry = compute_centered_window_geometry(
                self.root,
                content_height_px=int(self._main_frame.winfo_reqheight()),
                content_width_px=int(self._main_frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=44,
                default_w=629,
                default_h=940,
                screen_ratio_cap=0.95,
            )
            self.root.geometry(geometry)
        except _GEOMETRY_APPLY_ERRORS:
            return

    def _set_status(self, msg: str, *, ok: bool) -> None:
        color = "#00ff00" if ok else "#ff0000"
        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=""))

    def _read_reactive_brightness_percent(self) -> int | None:
        return _runtime.read_reactive_brightness_percent(self.config, logger=logger)

    def _read_reactive_trail_percent(self) -> int | None:
        return _runtime.read_reactive_trail_percent(self.config, logger=logger)

    def _sync_reactive_brightness_widgets(self) -> None:
        _runtime.sync_reactive_brightness_widgets(
            self._reactive_brightness_var,
            self._reactive_brightness_label,
            percent=self._read_reactive_brightness_percent(),
            tk_error=tk.TclError,
            logger=logger,
        )

    def _sync_reactive_trail_widgets(self) -> None:
        _runtime.sync_reactive_trail_widgets(
            self._reactive_trail_var,
            self._reactive_trail_label,
            percent=self._read_reactive_trail_percent(),
            tk_error=tk.TclError,
            logger=logger,
        )

    def _sync_color_wheel_brightness(self) -> None:
        if self.color_wheel is None:
            return
        _runtime.sync_color_wheel_brightness(
            self.color_wheel,
            self._use_manual_var,
            percent=self._read_reactive_brightness_percent(),
            tk_error=tk.TclError,
            logger=logger,
        )

    def _commit_color_to_config(self, color: tuple[int, int, int]) -> None:
        if not self._color_supported:
            return
        _runtime.commit_color_to_config(
            self.config,
            self._use_manual_var,
            color,
            tk_error=tk.TclError,
            logger=logger,
        )

    def _commit_brightness_to_config(self, brightness_percent: float | int | None) -> int | None:
        """Persist reactive typing brightness (pulse/highlight intensity)."""
        return _runtime.commit_brightness_to_config(self.config, brightness_percent, logger=logger)

    def _commit_trail_to_config(self, trail_percent: float | int | None) -> int | None:
        """Persist reactive wave thickness."""
        return _runtime.commit_trail_to_config(self.config, trail_percent, logger=logger)

    def _on_toggle_manual(self) -> None:
        reactive_color_interactions._on_toggle_manual(self, tk_error=tk.TclError, logger=logger)

    def _on_reactive_brightness_change(self, value: str | float) -> None:
        reactive_color_interactions._on_reactive_brightness_change(
            self,
            value,
            tk_error=tk.TclError,
            logger=logger,
            sync_color_wheel_brightness_fn=_runtime.sync_color_wheel_brightness,
            time_monotonic=time.monotonic,
        )

    def _on_reactive_brightness_release(self, _event=None) -> None:
        reactive_color_interactions._on_reactive_brightness_release(
            self,
            tk_error=tk.TclError,
            logger=logger,
            sync_color_wheel_brightness_fn=_runtime.sync_color_wheel_brightness,
            time_monotonic=time.monotonic,
        )

    def _on_reactive_trail_change(self, value: str | float) -> None:
        reactive_color_interactions._on_reactive_trail_change(self, value, tk_error=tk.TclError)

    def _on_reactive_trail_release(self, _event=None) -> None:
        reactive_color_interactions._on_reactive_trail_release(self, tk_error=tk.TclError)

    def _on_color_change(self, r: int, g: int, b: int, **meta: object) -> None:
        reactive_color_interactions._on_color_change(self, r, g, b, time_monotonic=time.monotonic, meta=meta)

    def _on_color_release(self, r: int, g: int, b: int, **meta: object) -> None:
        reactive_color_interactions._on_color_release(self, r, g, b, time_monotonic=time.monotonic, meta=meta)

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
