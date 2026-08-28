from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol, TypeAlias

Color: TypeAlias = tuple[int, int, int]
ColorApplyResult = bool | Literal["deferred"]
ColorApplyErrorTypes: TypeAlias = tuple[type[Exception], ...]


class _SetStatusFn(Protocol):
    def __call__(self, message: str, *, ok: bool) -> None: ...


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
