from __future__ import annotations

import logging
from typing import Callable, Mapping, Protocol, TypeAlias, cast

ReactiveColor: TypeAlias = tuple[int, int, int]
InteractionMeta: TypeAlias = Mapping[str, object]


class _ReadableVariable(Protocol):
    def get(self) -> object: ...


class _WritableVariable(Protocol):
    def set(self, value: object) -> None: ...


class _MutableVariable(_ReadableVariable, _WritableVariable, Protocol):
    pass


class _ConfigurableWidget(Protocol):
    def config(self, **kwargs: object) -> None: ...


class _BrightnessWheel(Protocol):
    def set_brightness_percent(self, percent: int) -> None: ...


class _BrightnessSyncFn(Protocol):
    def __call__(
        self,
        color_wheel: _BrightnessWheel | None,
        use_manual_var: _ReadableVariable,
        *,
        percent: int | None,
        tk_error: type[BaseException],
        logger: logging.Logger,
    ) -> None: ...


class _ReactiveManualConfig(Protocol):
    reactive_use_manual_color: bool


class _ReactiveColorDragState(Protocol):
    _last_drag_commit_ts: object
    _drag_commit_interval: object
    _last_drag_committed_color: object | None


class _ManualToggleGui(Protocol):
    _color_supported: bool
    _use_manual_var: _MutableVariable
    config: _ReactiveManualConfig


class _ReactiveBrightnessGui(Protocol):
    _reactive_brightness_label: _ConfigurableWidget
    _reactive_brightness_var: _ReadableVariable
    color_wheel: _BrightnessWheel | None
    _use_manual_var: _MutableVariable
    _last_drag_commit_ts: float
    _last_drag_committed_brightness: int | None

    def _commit_brightness_to_config(self, brightness_percent: float | int | None) -> int | None: ...

    def _set_status(self, msg: str, *, ok: bool) -> None: ...


class _ReactiveTrailGui(Protocol):
    _reactive_trail_label: _ConfigurableWidget
    _reactive_trail_var: _ReadableVariable

    def _commit_trail_to_config(self, trail_percent: float | int | None) -> int | None: ...

    def _set_status(self, msg: str, *, ok: bool) -> None: ...


class _ReactiveColorGui(Protocol):
    _color_supported: bool
    _last_drag_commit_ts: float
    _last_drag_committed_color: ReactiveColor | None

    def _commit_color_to_config(self, color: ReactiveColor) -> None: ...

    def _set_status(self, msg: str, *, ok: bool) -> None: ...


def _last_drag_commit_ts_or_default(gui: object) -> float:
    try:
        value = cast(_ReactiveColorDragState, gui)._last_drag_commit_ts
    except AttributeError:
        return 0.0
    return float(value or 0.0)


def _drag_commit_interval_or_default(gui: object) -> float:
    try:
        value = cast(_ReactiveColorDragState, gui)._drag_commit_interval
    except AttributeError:
        return 0.06
    return float(value or 0.06)


def _last_drag_committed_color_or_none(gui: object) -> ReactiveColor | None:
    try:
        value = cast(_ReactiveColorDragState, gui)._last_drag_committed_color
    except AttributeError:
        return None
    return cast(ReactiveColor | None, value)


def _meta_source(meta: InteractionMeta) -> str:
    return str(meta.get("source", "")).strip().lower()


def _on_toggle_manual(
    gui: _ManualToggleGui,
    *,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    if not gui._color_supported:
        try:
            gui._use_manual_var.set(False)
        except tk_error:
            pass
        return

    try:
        gui.config.reactive_use_manual_color = bool(gui._use_manual_var.get())
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        logger.debug("Failed to save reactive_use_manual_color", exc_info=True)


def _on_reactive_brightness_change(
    gui: _ReactiveBrightnessGui,
    value: str | float,
    *,
    tk_error: type[BaseException],
    logger: logging.Logger,
    sync_color_wheel_brightness_fn: _BrightnessSyncFn,
    time_monotonic: Callable[[], float],
) -> None:
    """Handle reactive brightness slider changes (0..100 UI scale)."""

    try:
        pct = float(value)
    except (TypeError, ValueError):
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    try:
        gui._reactive_brightness_label.config(text=f"{int(pct)}%")
    except tk_error:
        pass

    if not bool(gui._use_manual_var.get()):
        sync_color_wheel_brightness_fn(
            gui.color_wheel,
            gui._use_manual_var,
            percent=int(round(pct)),
            tk_error=tk_error,
            logger=logger,
        )

    last_drag_commit_ts = _last_drag_commit_ts_or_default(gui)
    drag_commit_interval = _drag_commit_interval_or_default(gui)
    now = time_monotonic()
    if (now - last_drag_commit_ts) < drag_commit_interval:
        return

    hw = gui._commit_brightness_to_config(pct)
    if hw is not None:
        gui._last_drag_commit_ts = now
        gui._last_drag_committed_brightness = int(round(hw * 2))


def _on_reactive_brightness_release(
    gui: _ReactiveBrightnessGui,
    *,
    tk_error: type[BaseException],
    logger: logging.Logger,
    sync_color_wheel_brightness_fn: _BrightnessSyncFn,
    time_monotonic: Callable[[], float],
) -> None:
    try:
        pct = float(gui._reactive_brightness_var.get())
    except (TypeError, ValueError, tk_error):
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    if not bool(gui._use_manual_var.get()):
        sync_color_wheel_brightness_fn(
            gui.color_wheel,
            gui._use_manual_var,
            percent=int(round(pct)),
            tk_error=tk_error,
            logger=logger,
        )

    hw = gui._commit_brightness_to_config(pct)
    if hw is None:
        gui._set_status("✗ Failed to save reactive brightness", ok=False)
        return

    pct_i = int(round(hw * 2))
    gui._last_drag_commit_ts = time_monotonic()
    gui._last_drag_committed_brightness = pct_i
    gui._set_status(f"✓ Saved reactive brightness {pct_i}%", ok=True)


def _on_reactive_trail_change(
    gui: _ReactiveTrailGui,
    value: str | float,
    *,
    tk_error: type[BaseException],
) -> None:
    """Handle wave thickness slider changes (1..100 UI scale)."""

    try:
        pct = float(value)
    except (TypeError, ValueError):
        pct = 50.0
    pct = max(1.0, min(100.0, pct))

    try:
        gui._reactive_trail_label.config(text=f"{int(pct)}%")
    except tk_error:
        pass


def _on_reactive_trail_release(gui: _ReactiveTrailGui, *, tk_error: type[BaseException]) -> None:
    try:
        pct = float(gui._reactive_trail_var.get())
    except (TypeError, ValueError, tk_error):
        pct = 50.0
    pct = max(1.0, min(100.0, pct))

    hw = gui._commit_trail_to_config(pct)
    if hw is None:
        gui._set_status("✗ Failed to save wave thickness", ok=False)
        return

    gui._set_status(f"✓ Saved wave thickness {hw}%", ok=True)


def _on_color_change(
    gui: _ReactiveColorGui,
    r: int,
    g: int,
    b: int,
    *,
    time_monotonic: Callable[[], float],
    meta: InteractionMeta,
) -> None:
    if not gui._color_supported:
        return
    if _meta_source(meta) == "brightness":
        return
    color = (int(r), int(g), int(b))

    last_drag_committed_color = _last_drag_committed_color_or_none(gui)
    last_drag_commit_ts = _last_drag_commit_ts_or_default(gui)
    drag_commit_interval = _drag_commit_interval_or_default(gui)
    now = time_monotonic()
    if last_drag_committed_color == color and (now - last_drag_commit_ts) < drag_commit_interval:
        return
    if (now - last_drag_commit_ts) < drag_commit_interval:
        return

    gui._commit_color_to_config(color)
    gui._last_drag_commit_ts = now
    gui._last_drag_committed_color = color


def _on_color_release(
    gui: _ReactiveColorGui,
    r: int,
    g: int,
    b: int,
    *,
    time_monotonic: Callable[[], float],
    meta: InteractionMeta,
) -> None:
    if not gui._color_supported:
        gui._set_status("✗ RGB color control is not supported on this backend", ok=False)
        return
    if _meta_source(meta) == "brightness":
        return
    color = (int(r), int(g), int(b))

    gui._commit_color_to_config(color)
    gui._last_drag_committed_color = color
    gui._last_drag_commit_ts = time_monotonic()
    gui._set_status(f"✓ Saved RGB({color[0]}, {color[1]}, {color[2]})", ok=True)
