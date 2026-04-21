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
    from src.gui.windows import _reactive_color_geometry as _geometry
    from src.gui.windows import _reactive_color_settings_adapter as _settings_adapter
    from src.gui.windows import _reactive_color_wiring as _wiring
except ImportError:
    # Fallback for direct execution (e.g. `python src/gui/windows/reactive_color.py`).
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.gui.windows import _reactive_color_runtime as _runtime
    from src.gui.windows import _reactive_color_geometry as _geometry
    from src.gui.windows import _reactive_color_settings_adapter as _settings_adapter
    from src.gui.windows import _reactive_color_wiring as _wiring


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
    _settings_adapter: _settings_adapter.ReactiveColorSettingsAdapter | None = None

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Reactive Typing Settings")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(520, 720)
        self.root.resizable(True, True)

        apply_clam_theme(self.root, include_checkbuttons=True, map_checkbutton_state=True)

        self.config = Config()
        self._settings_adapter: _settings_adapter.ReactiveColorSettingsAdapter | None = None
        self._get_settings_adapter().initialize_drag_state()

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
            **_wiring.build_description_section_kwargs(
                ttk_module=ttk,
                wrap_sync_errors=_WRAP_SYNC_ERRORS,
            ),
        )

        reactive_color_ui.build_reactive_window_ui(
            self,
            main,
            **_wiring.build_reactive_window_ui_kwargs(
                tk_module=tk,
                ttk_module=ttk,
                color_wheel_cls=ColorWheel,
                wrap_sync_errors=_WRAP_SYNC_ERRORS,
                tk_error=tk.TclError,
            ),
        )

        self._apply_geometry()
        self.root.after(50, self._apply_geometry)

        reactive_color_bootstrap.install_lifecycle_bindings(
            self,
            signal_module=signal,
            sigint=signal.SIGINT,
        )

    def _get_settings_adapter(self) -> _settings_adapter.ReactiveColorSettingsAdapter:
        adapter = self._settings_adapter
        if adapter is None:
            adapter = _settings_adapter.ReactiveColorSettingsAdapter(
                self,
                runtime_module=_runtime,
                tk_error=tk.TclError,
                logger=logger,
            )
            self._settings_adapter = adapter
        return adapter

    def _apply_geometry(self) -> None:
        _geometry.apply_centered_geometry(
            self.root,
            self._main_frame,
            compute_geometry_fn=compute_centered_window_geometry,
            apply_errors=_GEOMETRY_APPLY_ERRORS,
        )

    def _set_status(self, msg: str, *, ok: bool) -> None:
        self._get_settings_adapter().set_status(msg, ok=ok)

    def _read_reactive_brightness_percent(self) -> int | None:
        return self._get_settings_adapter().read_reactive_brightness_percent()

    def _read_reactive_trail_percent(self) -> int | None:
        return self._get_settings_adapter().read_reactive_trail_percent()

    def _sync_reactive_brightness_widgets(self) -> None:
        self._get_settings_adapter().sync_reactive_brightness_widgets()

    def _sync_reactive_trail_widgets(self) -> None:
        self._get_settings_adapter().sync_reactive_trail_widgets()

    def _sync_color_wheel_brightness(self) -> None:
        self._get_settings_adapter().sync_color_wheel_brightness()

    def _commit_color_to_config(self, color: tuple[int, int, int]) -> None:
        self._get_settings_adapter().commit_color_to_config(color)

    def _commit_brightness_to_config(self, brightness_percent: float | int | None) -> int | None:
        """Persist reactive typing brightness (pulse/highlight intensity)."""
        return self._get_settings_adapter().commit_brightness_to_config(brightness_percent)

    def _commit_trail_to_config(self, trail_percent: float | int | None) -> int | None:
        """Persist reactive wave thickness."""
        return self._get_settings_adapter().commit_trail_to_config(trail_percent)

    def _on_toggle_manual(self) -> None:
        reactive_color_interactions._on_toggle_manual(self, tk_error=tk.TclError, logger=logger)

    def _on_reactive_brightness_change(self, value: str | float) -> None:
        _wiring.dispatch_brightness_change(
            self,
            value,
            interactions_module=reactive_color_interactions,
            tk_error=tk.TclError,
            logger=logger,
            sync_color_wheel_brightness_fn=_runtime.sync_color_wheel_brightness,
            time_monotonic=time.monotonic,
        )

    def _on_reactive_brightness_release(self, _event=None) -> None:
        _wiring.dispatch_brightness_release(
            self,
            interactions_module=reactive_color_interactions,
            tk_error=tk.TclError,
            logger=logger,
            sync_color_wheel_brightness_fn=_runtime.sync_color_wheel_brightness,
            time_monotonic=time.monotonic,
        )

    def _on_reactive_trail_change(self, value: str | float) -> None:
        _wiring.dispatch_trail_change(
            self,
            value,
            interactions_module=reactive_color_interactions,
            tk_error=tk.TclError,
        )

    def _on_reactive_trail_release(self, _event=None) -> None:
        _wiring.dispatch_trail_release(
            self,
            interactions_module=reactive_color_interactions,
            tk_error=tk.TclError,
        )

    def _on_color_change(self, r: int, g: int, b: int, **meta: object) -> None:
        _wiring.dispatch_color_change(
            self,
            r,
            g,
            b,
            interactions_module=reactive_color_interactions,
            time_monotonic=time.monotonic,
            meta=meta,
        )

    def _on_color_release(self, r: int, g: int, b: int, **meta: object) -> None:
        _wiring.dispatch_color_release(
            self,
            r,
            g,
            b,
            interactions_module=reactive_color_interactions,
            time_monotonic=time.monotonic,
            meta=meta,
        )

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
