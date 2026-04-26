from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol


class _StatusLabel(Protocol):
    def config(self, **kwargs: object) -> object: ...


class _Root(Protocol):
    def after(self, delay: int, callback: Callable[[], object]) -> object: ...


class _Variable(Protocol):
    def get(self) -> object: ...

    def set(self, value: object) -> object: ...


class _ColorWheel(Protocol):
    def set_brightness_percent(self, pct: int) -> object: ...


class _ReactiveColorSettingsGUI(Protocol):
    status_label: _StatusLabel
    root: _Root
    config: object
    color_wheel: _ColorWheel | None
    _use_manual_var: _Variable
    _reactive_brightness_var: _Variable
    _reactive_brightness_label: _StatusLabel
    _reactive_trail_var: _Variable
    _reactive_trail_label: _StatusLabel
    _color_supported: bool
    _last_drag_commit_ts: float
    _last_drag_committed_color: tuple[int, int, int] | None
    _drag_commit_interval: float
    _last_drag_committed_brightness: int | None

    def _read_reactive_brightness_percent(self) -> int | None: ...

    def _read_reactive_trail_percent(self) -> int | None: ...


class _ReactiveColorRuntime(Protocol):
    def read_reactive_brightness_percent(self, config: object, *, logger: logging.Logger) -> int | None: ...

    def read_reactive_trail_percent(self, config: object, *, logger: logging.Logger) -> int | None: ...

    def sync_reactive_brightness_widgets(
        self,
        variable: _Variable,
        label: _StatusLabel,
        *,
        percent: int | None,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None: ...

    def sync_reactive_trail_widgets(
        self,
        variable: _Variable,
        label: _StatusLabel,
        *,
        percent: int | None,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None: ...

    def sync_color_wheel_brightness(
        self,
        color_wheel: _ColorWheel,
        use_manual_var: _Variable,
        *,
        percent: int | None,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None: ...

    def commit_color_to_config(
        self,
        config: object,
        use_manual_var: _Variable,
        color: tuple[int, int, int],
        *,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None: ...

    def commit_brightness_to_config(
        self,
        config: object,
        brightness_percent: float | int | None,
        *,
        logger: logging.Logger,
    ) -> int | None: ...

    def commit_trail_to_config(
        self,
        config: object,
        trail_percent: float | int | None,
        *,
        logger: logging.Logger,
    ) -> int | None: ...


class ReactiveColorSettingsAdapter:
    def __init__(
        self,
        gui: _ReactiveColorSettingsGUI,
        *,
        runtime_module: _ReactiveColorRuntime,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None:
        self._gui = gui
        self._runtime = runtime_module
        self._tk_error = tk_error
        self._logger = logger

    def initialize_drag_state(self) -> None:
        self._gui._last_drag_commit_ts = 0.0
        self._gui._last_drag_committed_color = None
        self._gui._drag_commit_interval = 0.06
        self._gui._last_drag_committed_brightness = None

    def set_status(self, msg: str, *, ok: bool) -> None:
        color = "#00ff00" if ok else "#ff0000"
        self._gui.status_label.config(text=msg, foreground=color)
        self._gui.root.after(2000, lambda: self._gui.status_label.config(text=""))

    def read_reactive_brightness_percent(self) -> int | None:
        return self._runtime.read_reactive_brightness_percent(self._gui.config, logger=self._logger)

    def read_reactive_trail_percent(self) -> int | None:
        return self._runtime.read_reactive_trail_percent(self._gui.config, logger=self._logger)

    def sync_reactive_brightness_widgets(self) -> None:
        self._runtime.sync_reactive_brightness_widgets(
            self._gui._reactive_brightness_var,
            self._gui._reactive_brightness_label,
            percent=self._gui._read_reactive_brightness_percent(),
            tk_error=self._tk_error,
            logger=self._logger,
        )

    def sync_reactive_trail_widgets(self) -> None:
        self._runtime.sync_reactive_trail_widgets(
            self._gui._reactive_trail_var,
            self._gui._reactive_trail_label,
            percent=self._gui._read_reactive_trail_percent(),
            tk_error=self._tk_error,
            logger=self._logger,
        )

    def sync_color_wheel_brightness(self) -> None:
        if self._gui.color_wheel is None:
            return

        self._runtime.sync_color_wheel_brightness(
            self._gui.color_wheel,
            self._gui._use_manual_var,
            percent=self._gui._read_reactive_brightness_percent(),
            tk_error=self._tk_error,
            logger=self._logger,
        )

    def commit_color_to_config(self, color: tuple[int, int, int]) -> None:
        if not self._gui._color_supported:
            return

        self._runtime.commit_color_to_config(
            self._gui.config,
            self._gui._use_manual_var,
            color,
            tk_error=self._tk_error,
            logger=self._logger,
        )

    def commit_brightness_to_config(self, brightness_percent: float | int | None) -> int | None:
        return self._runtime.commit_brightness_to_config(
            self._gui.config,
            brightness_percent,
            logger=self._logger,
        )

    def commit_trail_to_config(self, trail_percent: float | int | None) -> int | None:
        return self._runtime.commit_trail_to_config(
            self._gui.config,
            trail_percent,
            logger=self._logger,
        )
