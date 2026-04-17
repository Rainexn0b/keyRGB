from __future__ import annotations

from typing import Callable, Literal, Protocol, TypeAlias, cast

Color: TypeAlias = tuple[int, int, int]
ColorApplyResult = bool | Literal["deferred"]
ColorApplyErrorTypes: TypeAlias = tuple[type[Exception], ...]


class _SetStatusFn(Protocol):
    def __call__(self, message: str, *, ok: bool) -> None: ...


class _ApplyColorFn(Protocol):
    def __call__(self, r: int, g: int, b: int, brightness: int) -> ColorApplyResult: ...


class _GetColorFn(Protocol):
    def __call__(self) -> Color: ...


class _ColorWheel(Protocol):
    def get_color(self) -> Color: ...


class _ColorWheelHolder(Protocol):
    color_wheel: _ColorWheel | None


class _UniformConfig(Protocol):
    effect: str
    color: Color


class _UniformKeyboard(Protocol):
    def set_color(self, color: Color, *, brightness: int) -> None: ...


class _UniformDragState(Protocol):
    _pending_color: Color | None
    _last_drag_committed_color: Color | None
    _last_drag_commit_ts: float
    _drag_commit_interval: float


class _OnColorChangeGui(_UniformDragState, Protocol):
    _target_is_secondary: bool
    config: _UniformConfig

    def _store_secondary_color(self, color: Color) -> None: ...


class _ApplyColorGui(Protocol):
    kb: _UniformKeyboard | None


class _StatusfulUniformGui(Protocol):
    _target_label: object

    def _ensure_brightness_nonzero(self) -> int: ...

    def _commit_color_to_config(self, r: int, g: int, b: int) -> None: ...

    def _apply_color(self, r: int, g: int, b: int, brightness: int) -> ColorApplyResult: ...

    def _set_status(self, message: str, *, ok: bool) -> None: ...


class _OnColorReleaseGui(_UniformDragState, _StatusfulUniformGui, Protocol):
    pass


class _OnApplyGui(_StatusfulUniformGui, Protocol):
    _color_supported: bool


def _color_wheel_get_color_fn(gui: object) -> _GetColorFn | None:
    try:
        color_wheel = cast(_ColorWheelHolder, gui).color_wheel
    except AttributeError:
        return None
    if color_wheel is None:
        return None
    return color_wheel.get_color


def apply_status_message(*, target_label: str, color: Color, result: ColorApplyResult) -> tuple[str, bool]:
    r, g, b = color
    if result is True:
        return f"✓ Applied {target_label} RGB({r}, {g}, {b})", True
    if result == "deferred":
        return f"✓ Saved {target_label} RGB({r}, {g}, {b})", True
    return "✗ Error applying color", False


def set_apply_status(
    *,
    target_label: str,
    color: Color,
    result: ColorApplyResult,
    set_status_fn: _SetStatusFn,
) -> None:
    message, ok = apply_status_message(target_label=target_label, color=color, result=result)
    set_status_fn(message, ok=ok)


def on_color_change(
    gui: _OnColorChangeGui,
    r: int,
    g: int,
    b: int,
    *,
    time_monotonic: Callable[[], float],
) -> None:
    color: Color = (r, g, b)
    gui._pending_color = color

    now = time_monotonic()
    if gui._last_drag_committed_color == color and (now - gui._last_drag_commit_ts) < gui._drag_commit_interval:
        return
    if (now - gui._last_drag_commit_ts) < gui._drag_commit_interval:
        return

    if not gui._target_is_secondary and gui.config.effect != "none":
        gui.config.effect = "none"
    if gui._target_is_secondary:
        gui._store_secondary_color(color)
    else:
        gui.config.color = color
    gui._last_drag_commit_ts = now
    gui._last_drag_committed_color = color


def apply_color(
    gui: _ApplyColorGui,
    r: int,
    g: int,
    b: int,
    brightness: int,
    *,
    is_device_busy_fn: Callable[[BaseException], bool],
    log_color_apply_failure_fn: Callable[[Exception], None],
    device_apply_errors: ColorApplyErrorTypes,
    device_write_errors: ColorApplyErrorTypes,
) -> ColorApplyResult:
    if gui.kb is None:
        return "deferred"

    try:
        gui.kb.set_color((r, g, b), brightness=brightness)
        return True
    except OSError as exc:
        if is_device_busy_fn(exc):
            gui.kb = None
            return "deferred"
        log_color_apply_failure_fn(exc)
        return False
    except device_apply_errors as exc:
        log_color_apply_failure_fn(exc)
        return False
    except device_write_errors as exc:
        log_color_apply_failure_fn(exc)
        return False


def on_color_release(
    gui: _OnColorReleaseGui,
    r: int,
    g: int,
    b: int,
    *,
    time_monotonic: Callable[[], float],
    apply_color_fn: _ApplyColorFn | None = None,
    set_status_fn: _SetStatusFn | None = None,
) -> None:
    color: Color = (r, g, b)
    brightness = int(gui._ensure_brightness_nonzero())
    gui._commit_color_to_config(r, g, b)

    gui._last_drag_committed_color = color
    gui._last_drag_commit_ts = time_monotonic()

    active_apply_color_fn = gui._apply_color if apply_color_fn is None else apply_color_fn
    active_set_status_fn = gui._set_status if set_status_fn is None else set_status_fn
    result = active_apply_color_fn(r, g, b, brightness)
    set_apply_status(
        target_label=str(gui._target_label),
        color=color,
        result=result,
        set_status_fn=active_set_status_fn,
    )


def on_apply(
    gui: _OnApplyGui,
    *,
    get_color_fn: _GetColorFn | None = None,
    apply_color_fn: _ApplyColorFn | None = None,
    set_status_fn: _SetStatusFn | None = None,
) -> None:
    active_get_color_fn = get_color_fn if get_color_fn is not None else _color_wheel_get_color_fn(gui)
    active_set_status_fn = gui._set_status if set_status_fn is None else set_status_fn
    if not gui._color_supported or active_get_color_fn is None:
        active_set_status_fn("✗ RGB color control is not supported on this backend", ok=False)
        return
    r, g, b = active_get_color_fn()
    brightness = int(gui._ensure_brightness_nonzero())
    gui._commit_color_to_config(r, g, b)

    active_apply_color_fn = gui._apply_color if apply_color_fn is None else apply_color_fn
    result = active_apply_color_fn(r, g, b, brightness)
    set_apply_status(
        target_label=str(gui._target_label),
        color=(r, g, b),
        result=result,
        set_status_fn=active_set_status_fn,
    )
