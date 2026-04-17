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
from src.core.secondary_device_routes import SecondaryDeviceRoute, route_for_backend_name, route_for_device_type
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
    from src.gui.windows import _uniform_color_ui as uniform_color_ui
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/uniform.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.gui.widgets.color_wheel import ColorWheel
    from src.core.config import Config
    from src.gui.windows import _uniform_color_bootstrap as uniform_color_bootstrap
    from src.gui.windows import _uniform_color_interactions as uniform_color_interactions
    from src.gui.windows import _uniform_color_ui as uniform_color_ui


class UniformColorGUI:
    """Simple GUI for selecting a uniform keyboard color."""

    _secondary_route: SecondaryDeviceRoute | None = None

    def __init__(self):
        self.target_context = (
            str(os.environ.get("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard") or "keyboard").strip().lower()
        )
        self.requested_backend = str(os.environ.get("KEYRGB_UNIFORM_BACKEND", "") or "").strip().lower() or None
        self._secondary_route = self._resolve_secondary_route()
        self._target_is_secondary = self._secondary_route is not None
        self._target_label = (
            str(self._secondary_route.display_name) if self._secondary_route is not None else "Keyboard"
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
        backend = self._select_backend_best_effort()
        self._color_supported = self._probe_color_support(backend)
        self.kb = self._acquire_device_best_effort(backend)

        uniform_color_ui.build_uniform_window_ui(
            self,
            ttk_module=ttk,
            color_wheel_cls=ColorWheel,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
            tk_widget_state_errors=_TK_WIDGET_STATE_ERRORS,
        )

        self._apply_geometry()
        self.root.after(50, self._apply_geometry)

        self._pending_color = None
        self._last_drag_commit_ts = 0.0
        self._last_drag_committed_color = None

        # Throttle config writes while dragging (seconds)
        self._drag_commit_interval = 0.06

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
        return uniform_color_bootstrap.select_backend_best_effort(
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
        return uniform_color_bootstrap.probe_color_support(backend, logger=logger)

    def _acquire_device_best_effort(self, backend):
        return uniform_color_bootstrap.acquire_device_best_effort(
            backend,
            is_device_busy_fn=is_device_busy,
            logger=logger,
        )

    def _log_color_apply_failure(self, exc: Exception) -> None:
        if os.environ.get("KEYRGB_DEBUG"):
            logger.exception("Error setting color")
            return
        logger.error("Error setting color: %s", exc)

    def _set_status(self, msg: str, *, ok: bool) -> None:
        color = "#00ff00" if ok else "#ff0000"
        self.status_label.config(text=msg, foreground=color)
        self.root.after(2000, lambda: self.status_label.config(text=""))

    def _ensure_brightness_nonzero(self) -> int:
        brightness = int(self._current_brightness())
        if brightness == 0:
            brightness = 25
            self._store_brightness(brightness)
        return brightness

    def _commit_color_to_config(self, r: int, g: int, b: int) -> None:
        if self._target_is_secondary:
            self._store_secondary_color((r, g, b))
            return

        # Stop any running effects first, then save the color (auto-saves)
        self.config.effect = "none"
        self.config.color = (r, g, b)

    def _initial_color(self) -> tuple[int, int, int]:
        if self._target_is_secondary:
            return self._current_secondary_color()
        return tuple(self.config.color) if isinstance(self.config.color, list) else self.config.color

    def _current_brightness(self) -> int:
        if not self._target_is_secondary:
            return int(self.config.brightness)

        getter = getattr(self.config, "get_secondary_device_brightness", None)
        if callable(getter) and self._secondary_route is not None:
            return int(
                getter(
                    str(self._secondary_route.state_key),
                    fallback_keys=tuple(filter(None, (self._secondary_route.config_brightness_attr,))),
                    default=25,
                )
            )

        if self._secondary_route is not None and self._secondary_route.config_brightness_attr:
            return int(getattr(self.config, self._secondary_route.config_brightness_attr, 25) or 25)
        return 25

    def _store_brightness(self, brightness: int) -> None:
        if not self._target_is_secondary:
            self.config.brightness = brightness
            return

        if self._secondary_route is None:
            return

        setter = getattr(self.config, "set_secondary_device_brightness", None)
        if callable(setter):
            setter(
                str(self._secondary_route.state_key),
                int(brightness),
                compatibility_key=self._secondary_route.config_brightness_attr,
            )
            return

        if self._secondary_route.config_brightness_attr:
            setattr(self.config, self._secondary_route.config_brightness_attr, int(brightness))

    def _current_secondary_color(self) -> tuple[int, int, int]:
        if self._secondary_route is None:
            return (255, 0, 0)

        getter = getattr(self.config, "get_secondary_device_color", None)
        if callable(getter):
            return tuple(
                getter(
                    str(self._secondary_route.state_key),
                    fallback_keys=tuple(filter(None, (self._secondary_route.config_color_attr,))),
                    default=(255, 0, 0),
                )
            )

        if self._secondary_route.config_color_attr:
            return tuple(getattr(self.config, self._secondary_route.config_color_attr, (255, 0, 0)))
        return (255, 0, 0)

    def _store_secondary_color(self, color: tuple[int, int, int]) -> None:
        if self._secondary_route is None:
            return

        setter = getattr(self.config, "set_secondary_device_color", None)
        if callable(setter):
            setter(
                str(self._secondary_route.state_key),
                color,
                compatibility_key=self._secondary_route.config_color_attr,
                default=(255, 0, 0),
            )
            return

        if self._secondary_route.config_color_attr:
            setattr(self.config, self._secondary_route.config_color_attr, color)

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
