"""Uniform Color GUI - Simple color wheel for selecting a single keyboard color."""

from __future__ import annotations

import logging
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, TypeAlias, cast

from keyrgb.core.runtime.hardware_ownership import acquire_hardware_control_lock, release_hardware_control_lock
from keyrgb.core.runtime.imports import ensure_repo_root_on_sys_path
from keyrgb.core.utils.exceptions import is_device_busy
from keyrgb.gui.theme import apply_clam_theme
from keyrgb.gui.utils.tk_async import TkAsyncCoordinator, submit_gui_work
from keyrgb.gui.utils.window_geometry import compute_centered_window_geometry
from keyrgb.gui.utils.window_icon import apply_keyrgb_window_icon

if TYPE_CHECKING:
    from keyrgb.gui.windows._uniform_color_state import _UniformStatusLabel

logger = logging.getLogger(__name__)
_DEVICE_APPLY_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)
_UNIFORM_DEVICE_WRITE_ERRORS = (AttributeError, LookupError, RuntimeError, TypeError, ValueError)
_TK_WIDGET_STATE_ERRORS = (AttributeError, RuntimeError, tk.TclError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_WRAP_SYNC_ERRORS = (RuntimeError, tk.TclError, TypeError, ValueError)
_DEVICE_CLOSE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

try:
    from keyrgb.core.config import Config
    from keyrgb.gui.widgets.color_wheel import ColorWheel
    from keyrgb.gui.windows import (
        _uniform_color_bootstrap as uniform_color_bootstrap,
        _uniform_color_interactions as uniform_color_interactions,
        _uniform_color_state as uniform_color_state,
        _uniform_color_ui as uniform_color_ui,
        _uniform_init_adapter as uniform_init_adapter,
    )
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/uniform.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from keyrgb.core.config import Config
    from keyrgb.gui.widgets.color_wheel import ColorWheel
    from keyrgb.gui.windows import (
        _uniform_color_bootstrap as uniform_color_bootstrap,
        _uniform_color_interactions as uniform_color_interactions,
        _uniform_color_state as uniform_color_state,
        _uniform_color_ui as uniform_color_ui,
        _uniform_init_adapter as uniform_init_adapter,
    )


SecondaryDeviceRoute: TypeAlias = uniform_color_bootstrap.SecondaryDeviceRoute
select_backend = uniform_color_bootstrap.select_backend
route_for_backend_name = uniform_color_bootstrap.route_for_backend_name
route_for_device_type = uniform_color_bootstrap.route_for_device_type


class UniformColorGUI:
    """Simple GUI for selecting a uniform keyboard color."""

    _secondary_route: SecondaryDeviceRoute | None = None
    _main_frame: ttk.Frame
    status_label: _UniformStatusLabel

    def __init__(self):
        target_state = uniform_init_adapter.resolve_target_route_state(
            target_context=os.environ.get("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard"),
            requested_backend=os.environ.get("KEYRGB_UNIFORM_BACKEND", ""),
            resolve_secondary_route_fn=self._resolve_secondary_route,
        )
        self.target_context = target_state.target_context
        self.requested_backend = target_state.requested_backend
        self._secondary_route = target_state.secondary_route
        self._target_is_secondary = target_state.target_is_secondary
        self._target_label = target_state.target_label

        self.root = tk.Tk()
        self.tk_jobs = TkAsyncCoordinator()
        self.root.title(f"KeyRGB - {self._target_label} Color")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(460, 520)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        # Initialize config (tray app will apply changes if it's running)
        self.config = Config()

        # Try to acquire device for standalone mode; if tray app owns it, we'll defer.
        tray_managed = os.environ.get("KEYRGB_TRAY_MANAGED_GUI", "").strip().lower() in {"1", "true", "yes", "on"}
        self._owns_hardware_lock = False if tray_managed else acquire_hardware_control_lock()
        init_state = uniform_init_adapter.initialize_device_bootstrap_state(
            secondary_route=self._secondary_route,
            requested_backend=getattr(self, "requested_backend", None),
            select_backend_fn=select_backend,
            is_device_busy_fn=is_device_busy,
            logger=logger,
            allow_hardware=self._owns_hardware_lock,
        )
        self._backend = init_state.backend
        self._color_supported = init_state.color_supported
        self.kb = init_state.device
        if self.kb is None and self._owns_hardware_lock:
            release_hardware_control_lock()
            self._owns_hardware_lock = False

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
        protocol = getattr(self.root, "protocol", None)
        if callable(protocol):
            protocol("WM_DELETE_WINDOW", self._on_close)

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
            secondary_route=vars(self).get("_secondary_route"),
            is_device_busy_fn=is_device_busy,
            logger=logger,
        )

    def _log_color_apply_failure(self, exc: Exception) -> None:
        uniform_init_adapter.log_color_apply_failure(
            exc,
            debug_enabled=bool(os.environ.get("KEYRGB_DEBUG")),
            logger=logger,
        )

    def _set_status(self, message: str, *, ok: bool) -> None:
        uniform_color_state.set_status(self, message, ok=ok)

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

    def _schedule_color_apply(self, r: int, g: int, b: int, brightness: int) -> None:
        color = (r, g, b)

        def work() -> uniform_color_interactions.ColorApplyResult:
            return self._apply_color(r, g, b, brightness)

        def on_done(result: uniform_color_interactions.ColorApplyResult) -> None:
            uniform_color_interactions.set_apply_status(
                target_label=str(self._target_label),
                color=color,
                result=result,
                set_status_fn=self._set_status,
            )

        submit_gui_work(self, getattr(self, "root", None), work, on_done)

    def _on_color_release(self, r, g, b):
        brightness = int(self._ensure_brightness_nonzero())
        self._commit_color_to_config(r, g, b)
        self._last_drag_committed_color = (r, g, b)
        self._last_drag_commit_ts = time.monotonic()
        self._schedule_color_apply(r, g, b, brightness)

    def _on_apply(self):
        if not self._color_supported or self.color_wheel is None:
            self._set_status("✗ RGB color control is not supported on this backend", ok=False)
            return
        r, g, b = self.color_wheel.get_color()
        brightness = int(self._ensure_brightness_nonzero())
        self._commit_color_to_config(r, g, b)
        self._schedule_color_apply(r, g, b, brightness)

    def _on_close(self):
        try:
            self.tk_jobs.cancel()
        except AttributeError:
            pass
        device = getattr(self, "kb", None)
        self.kb = None
        close = getattr(device, "close", None)
        if callable(close):
            try:
                close()
            except _DEVICE_CLOSE_ERRORS:
                logger.debug("Failed to close uniform color device", exc_info=True)
        try:
            owns_hardware_lock = bool(self._owns_hardware_lock)
        except AttributeError:
            owns_hardware_lock = False
        if owns_hardware_lock:
            release_hardware_control_lock()
            self._owns_hardware_lock = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main() -> None:
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    UniformColorGUI().run()


if __name__ == "__main__":
    main()
