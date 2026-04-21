#!/usr/bin/env python3
"""Uniform Color GUI - Simple color wheel for selecting a single keyboard color."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from src.core.runtime.imports import ensure_repo_root_on_sys_path
from src.core.utils.exceptions import is_device_busy
from src.gui.utils.window_geometry import compute_centered_window_geometry
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme

logger = logging.getLogger(__name__)
_DEVICE_APPLY_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)
_UNIFORM_DEVICE_WRITE_ERRORS = (AttributeError, LookupError, RuntimeError, TypeError, ValueError)
_TK_WIDGET_STATE_ERRORS = (AttributeError, RuntimeError, tk.TclError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_WRAP_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)

try:
    from src.gui.widgets.color_wheel import ColorWheel
    from src.core.config import Config
    from src.gui.windows import _uniform_color_bootstrap as uniform_color_bootstrap
    from src.gui.windows import _uniform_color_interactions as uniform_color_interactions
    from src.gui.windows import _uniform_init_adapter as uniform_init_adapter
    from src.gui.windows import _uniform_color_state as uniform_color_state
    from src.gui.windows import _uniform_color_ui as uniform_color_ui
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/uniform.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.gui.widgets.color_wheel import ColorWheel
    from src.core.config import Config
    from src.gui.windows import _uniform_color_bootstrap as uniform_color_bootstrap
    from src.gui.windows import _uniform_color_interactions as uniform_color_interactions
    from src.gui.windows import _uniform_init_adapter as uniform_init_adapter
    from src.gui.windows import _uniform_color_state as uniform_color_state
    from src.gui.windows import _uniform_color_ui as uniform_color_ui


SecondaryDeviceRoute = uniform_color_bootstrap.SecondaryDeviceRoute
select_backend = uniform_color_bootstrap.select_backend
route_for_backend_name = uniform_color_bootstrap.route_for_backend_name
route_for_device_type = uniform_color_bootstrap.route_for_device_type


class UniformColorGUI:
    """Simple GUI for selecting a uniform keyboard color."""

    _secondary_route: SecondaryDeviceRoute | None = None

    def __init__(self):
        uniform_color_state.initialize_target_route_state(
            self,
            target_context=os.environ.get("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard"),
            requested_backend=os.environ.get("KEYRGB_UNIFORM_BACKEND", ""),
            resolve_secondary_route_fn=self._resolve_secondary_route,
        )

        self.root = tk.Tk()
        self.root.title(f"KeyRGB - {self._target_label} Color")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(460, 520)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        # Initialize config (tray app will apply changes if it's running)
        self.config = Config()

        # Try to acquire device for standalone mode; if tray app owns it, we'll defer.
        init_state = uniform_init_adapter.initialize_device_bootstrap_state(
            secondary_route=self._secondary_route,
            requested_backend=getattr(self, "requested_backend", None),
            select_backend_fn=select_backend,
            is_device_busy_fn=is_device_busy,
            logger=logger,
        )
        self._backend = init_state.backend
        self._color_supported = init_state.color_supported
        self.kb = init_state.device

        uniform_color_ui.build_uniform_window_ui(
            self,
            ttk_module=ttk,
            color_wheel_cls=ColorWheel,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
            tk_widget_state_errors=_TK_WIDGET_STATE_ERRORS,
        )

        self._apply_geometry()
        self.root.after(50, self._apply_geometry)

        uniform_color_state.initialize_drag_state(self, drag_commit_interval=0.06)

    def _apply_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            geometry = compute_centered_window_geometry(
                self.root,
                content_height_px=int(self._main_frame.winfo_reqheight()),
                content_width_px=int(self._main_frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=40,
                default_w=520,
                default_h=610,
                screen_ratio_cap=0.95,
            )
            self.root.geometry(geometry)
        except _GEOMETRY_APPLY_ERRORS:
            return

    def _select_backend_best_effort(self):
        return uniform_init_adapter.select_backend_best_effort(
            self._secondary_route,
            requested_backend=getattr(self, "requested_backend", None),
            select_backend_fn=select_backend,
            logger=logger,
        )

    def _resolve_secondary_route(self):
        return uniform_color_bootstrap.resolve_secondary_route(
            target_context=str(getattr(self, "target_context", "keyboard") or "keyboard"),
            requested_backend=getattr(self, "requested_backend", None),
            route_for_backend_name_fn=route_for_backend_name,
            route_for_device_type_fn=route_for_device_type,
        )

    def _probe_color_support(self, backend) -> bool:
        return uniform_init_adapter.probe_color_support(backend, logger=logger)

    def _acquire_device_best_effort(self, backend):
        return uniform_init_adapter.acquire_device_best_effort(
            backend,
            is_device_busy_fn=is_device_busy,
            logger=logger,
        )

    def _log_color_apply_failure(self, exc: Exception) -> None:
        uniform_init_adapter.log_color_apply_failure(
            exc,
            debug_enabled=bool(os.environ.get("KEYRGB_DEBUG")),
            logger=logger,
        )

    def _set_status(self, msg: str, *, ok: bool) -> None:
        uniform_color_state.set_status(self, msg, ok=ok)

    def _ensure_brightness_nonzero(self) -> int:
        return uniform_color_state.ensure_brightness_nonzero(self)

    def _commit_color_to_config(self, r: int, g: int, b: int) -> None:
        uniform_color_state.commit_color_to_config(self, r, g, b)

    def _initial_color(self) -> tuple[int, int, int]:
        return uniform_color_state.initial_color(self)

    def _current_brightness(self) -> int:
        return uniform_color_state.current_brightness(self)

    def _store_brightness(self, brightness: int) -> None:
        uniform_color_state.store_brightness(self, brightness)

    def _current_secondary_color(self) -> tuple[int, int, int]:
        return uniform_color_state.current_secondary_color(self)

    def _store_secondary_color(self, color: tuple[int, int, int]) -> None:
        uniform_color_state.store_secondary_color(self, color)

    def _on_color_change(self, r, g, b):
        uniform_color_interactions.on_color_change(self, r, g, b, time_monotonic=time.monotonic)

    def _apply_color(self, r, g, b, brightness):
        return uniform_color_interactions.apply_color(
            self,
            r,
            g,
            b,
            brightness,
            is_device_busy_fn=is_device_busy,
            log_color_apply_failure_fn=self._log_color_apply_failure,
            device_apply_errors=_DEVICE_APPLY_ERRORS,
            device_write_errors=_UNIFORM_DEVICE_WRITE_ERRORS,
        )

    def _on_color_release(self, r, g, b):
        uniform_color_interactions.on_color_release(
            self,
            r,
            g,
            b,
            time_monotonic=time.monotonic,
            apply_color_fn=self._apply_color,
            set_status_fn=self._set_status,
        )

    def _on_apply(self):
        uniform_color_interactions.on_apply(
            self,
            get_color_fn=None if self.color_wheel is None else self.color_wheel.get_color,
            apply_color_fn=self._apply_color,
            set_status_fn=self._set_status,
        )

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
