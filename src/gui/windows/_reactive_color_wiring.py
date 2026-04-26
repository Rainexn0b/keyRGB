from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def dispatch_brightness_change(
    gui: object,
    value: str | float,
    *,
    interactions_module: object,
    tk_error: type[BaseException],
    logger: object,
    sync_color_wheel_brightness_fn: object,
    time_monotonic: Callable[[], float],
) -> None:
    interactions_module._on_reactive_brightness_change(
        gui,
        value,
        **build_brightness_interaction_kwargs(
            tk_error=tk_error,
            logger=logger,
            sync_color_wheel_brightness_fn=sync_color_wheel_brightness_fn,
            time_monotonic=time_monotonic,
        ),
    )


def dispatch_brightness_release(
    gui: object,
    *,
    interactions_module: object,
    tk_error: type[BaseException],
    logger: object,
    sync_color_wheel_brightness_fn: object,
    time_monotonic: Callable[[], float],
) -> None:
    interactions_module._on_reactive_brightness_release(
        gui,
        **build_brightness_interaction_kwargs(
            tk_error=tk_error,
            logger=logger,
            sync_color_wheel_brightness_fn=sync_color_wheel_brightness_fn,
            time_monotonic=time_monotonic,
        ),
    )


def dispatch_trail_change(
    gui: object,
    value: str | float,
    *,
    interactions_module: object,
    tk_error: type[BaseException],
) -> None:
    interactions_module._on_reactive_trail_change(
        gui,
        value,
        **build_trail_interaction_kwargs(tk_error=tk_error),
    )


def dispatch_trail_release(
    gui: object,
    *,
    interactions_module: object,
    tk_error: type[BaseException],
) -> None:
    interactions_module._on_reactive_trail_release(
        gui,
        **build_trail_interaction_kwargs(tk_error=tk_error),
    )


def dispatch_color_change(
    gui: object,
    r: int,
    g: int,
    b: int,
    *,
    interactions_module: object,
    time_monotonic: Callable[[], float],
    meta: Mapping[str, object],
) -> None:
    interactions_module._on_color_change(
        gui,
        r,
        g,
        b,
        **build_color_interaction_kwargs(time_monotonic=time_monotonic, meta=meta),
    )


def dispatch_color_release(
    gui: object,
    r: int,
    g: int,
    b: int,
    *,
    interactions_module: object,
    time_monotonic: Callable[[], float],
    meta: Mapping[str, object],
) -> None:
    interactions_module._on_color_release(
        gui,
        r,
        g,
        b,
        **build_color_interaction_kwargs(time_monotonic=time_monotonic, meta=meta),
    )


def build_description_section_kwargs(
    *, ttk_module: object, wrap_sync_errors: tuple[type[BaseException], ...]
) -> dict[str, object]:
    return {
        "ttk_module": ttk_module,
        "wrap_sync_errors": wrap_sync_errors,
    }


def build_reactive_window_ui_kwargs(
    *,
    tk_module: object,
    ttk_module: object,
    color_wheel_cls: object,
    wrap_sync_errors: tuple[type[BaseException], ...],
    tk_error: type[BaseException],
) -> dict[str, object]:
    return {
        "tk_module": tk_module,
        "ttk_module": ttk_module,
        "color_wheel_cls": color_wheel_cls,
        "wrap_sync_errors": wrap_sync_errors,
        "tk_error": tk_error,
    }


def build_brightness_interaction_kwargs(
    *,
    tk_error: type[BaseException],
    logger: object,
    sync_color_wheel_brightness_fn: object,
    time_monotonic: Callable[[], float],
) -> dict[str, object]:
    return {
        "tk_error": tk_error,
        "logger": logger,
        "sync_color_wheel_brightness_fn": sync_color_wheel_brightness_fn,
        "time_monotonic": time_monotonic,
    }


def build_color_interaction_kwargs(
    *,
    time_monotonic: Callable[[], float],
    meta: Mapping[str, object],
) -> dict[str, object]:
    return {
        "time_monotonic": time_monotonic,
        "meta": meta,
    }


def build_trail_interaction_kwargs(*, tk_error: type[BaseException]) -> dict[str, Any]:
    return {"tk_error": tk_error}
