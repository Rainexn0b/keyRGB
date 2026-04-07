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
from src.core.secondary_device_routes import route_for_backend_name, route_for_device_type
from src.core.utils.exceptions import is_device_busy
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.utils.window_centering import center_window_on_screen
from src.gui.theme import apply_clam_theme


logger = logging.getLogger(__name__)
_BACKEND_CAPABILITY_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_BACKEND_SELECTION_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)
_DEVICE_ACQUISITION_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_DEVICE_APPLY_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)
_TK_WIDGET_STATE_ERRORS = (AttributeError, RuntimeError, tk.TclError)

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
        desired_w, desired_h = 520, 610
        max_w = int(self.root.winfo_screenwidth() * 0.95)
        max_h = int(self.root.winfo_screenheight() * 0.95)
        w = min(desired_w, max_w)
        h = min(desired_h, max_h)
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(w, h)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        # Initialize config (tray app will apply changes if it's running)
        self.config = Config()

        # Try to acquire device for standalone mode; if tray app owns it, we'll defer.
        backend = self._select_backend_best_effort()
        self._color_supported = self._probe_color_support(backend)
        self.kb = self._acquire_device_best_effort(backend)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill="both", expand=True)

        title = ttk.Label(main_frame, text=f"Select Uniform {self._target_label} Color", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        if not self._color_supported:
            msg = ttk.Label(
                main_frame,
                text=(
                    "RGB color control is not available with the currently selected backend.\n\n"
                    "This usually means the sysfs LED driver only exposes brightness (no writable RGB attribute).\n"
                    "You can still adjust brightness from the tray, or switch to a backend that supports RGB color."
                ),
                font=("Sans", 9),
                justify="left",
                wraplength=max(200, w - 48),
            )
            msg.pack(pady=(10, 16), fill="x")
            self.color_wheel = None
        else:
            self.color_wheel = ColorWheel(
                main_frame,
                size=350,
                initial_color=self._initial_color(),
                callback=self._on_color_change,
                release_callback=self._on_color_release,
            )
            self.color_wheel.pack()

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill="x")

        apply_btn = ttk.Button(button_frame, text="Apply", command=self._on_apply)
        if not self._color_supported:
            try:
                apply_btn.configure(state="disabled")
            except _TK_WIDGET_STATE_ERRORS:
                pass
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

    def _select_backend_best_effort(self):
        try:
            route = getattr(self, "_secondary_route", None)
            if route is not None:
                return route.get_backend()
            return select_backend(requested=self.requested_backend)
        except _BACKEND_SELECTION_ERRORS:
            logger.debug(
                "Failed to select backend for the uniform color window; falling back to config-only mode",
                exc_info=True,
            )
            return None

    def _resolve_secondary_route(self):
        route = route_for_backend_name(self.requested_backend)
        if route is not None:
            return route

        device_type = self.target_context.split(":", 1)[0].strip().lower()
        if not device_type or device_type == "keyboard":
            return None
        return route_for_device_type(device_type)

    def _probe_color_support(self, backend) -> bool:
        if backend is None:
            return True

        try:
            caps = backend.capabilities()
            return bool(getattr(caps, "color", True)) if caps is not None else True
        except _BACKEND_CAPABILITY_ERRORS:
            logger.debug(
                "Failed to probe backend capabilities for the uniform color window; assuming RGB support",
                exc_info=True,
            )
            return True

    def _acquire_device_best_effort(self, backend):
        if backend is None:
            return None

        try:
            return backend.get_device()
        except OSError as exc:
            if is_device_busy(exc):
                logger.debug("Uniform color window is deferring to the tray-owned device handle", exc_info=True)
                return None
            logger.debug(
                "Failed to acquire a device for the uniform color window; falling back to config-only mode",
                exc_info=True,
            )
            return None
        except _DEVICE_ACQUISITION_ERRORS:
            logger.debug(
                "Failed to acquire a device for the uniform color window; falling back to config-only mode",
                exc_info=True,
            )
            return None

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
                legacy_key=self._secondary_route.config_brightness_attr,
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
                legacy_key=self._secondary_route.config_color_attr,
                default=(255, 0, 0),
            )
            return

        if self._secondary_route.config_color_attr:
            setattr(self.config, self._secondary_route.config_color_attr, color)

    def _on_color_change(self, r, g, b):
        """Handle color wheel changes (during drag)."""
        color = (r, g, b)
        self._pending_color = color

        now = time.monotonic()
        if self._last_drag_committed_color == color and (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return
        if (now - self._last_drag_commit_ts) < self._drag_commit_interval:
            return

        if not self._target_is_secondary and self.config.effect != "none":
            self.config.effect = "none"
        if self._target_is_secondary:
            self._store_secondary_color(color)
        else:
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
            self._log_color_apply_failure(e)
            return False
        except _DEVICE_APPLY_ERRORS as e:
            self._log_color_apply_failure(e)
            return False
        except Exception as e:  # @quality-exception exception-transparency: uniform color apply crosses backend/runtime device writes; GUI apply must remain best-effort
            self._log_color_apply_failure(e)
            return False

    def _on_color_release(self, r, g, b):
        """Handle color wheel release (apply and save)."""
        brightness = self._ensure_brightness_nonzero()
        self._commit_color_to_config(r, g, b)

        self._last_drag_committed_color = (r, g, b)
        self._last_drag_commit_ts = time.monotonic()

        result = self._apply_color(r, g, b, brightness)
        if result is True:
            self._set_status(f"✓ Applied {self._target_label} RGB({r}, {g}, {b})", ok=True)
        elif result == "deferred":
            self._set_status(f"✓ Saved {self._target_label} RGB({r}, {g}, {b})", ok=True)
        else:
            self._set_status("✗ Error applying color", ok=False)

    def _on_apply(self):
        """Apply the selected color to the keyboard."""
        if not self._color_supported or self.color_wheel is None:
            self._set_status("✗ RGB color control is not supported on this backend", ok=False)
            return

        r, g, b = self.color_wheel.get_color()

        brightness = self._ensure_brightness_nonzero()
        self._commit_color_to_config(r, g, b)

        result = self._apply_color(r, g, b, brightness)
        if result is True:
            self._set_status(f"✓ Applied {self._target_label} RGB({r}, {g}, {b})", ok=True)
        elif result == "deferred":
            self._set_status(f"✓ Saved {self._target_label} RGB({r}, {g}, {b})", ok=True)
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
