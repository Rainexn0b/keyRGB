from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast


def _dispatch_handler(interactions_module: object, handler_name: str) -> Callable[..., None]:
    return cast(Callable[..., None], getattr(interactions_module, handler_name))


def _build_value_dispatcher(
    handler_name: str,
    kwargs_builder: Callable[..., dict[str, object]],
) -> Callable[..., None]:
    def _dispatch(
        gui: object,
        value: str | float,
        *,
        interactions_module: object,
        **kwargs: object,
    ) -> None:
        _dispatch_handler(interactions_module, handler_name)(gui, value, **kwargs_builder(**kwargs))

    _dispatch.__name__ = handler_name.removeprefix("_on_")
    return _dispatch


def _build_release_dispatcher(
    handler_name: str,
    kwargs_builder: Callable[..., dict[str, object]],
) -> Callable[..., None]:
    def _dispatch(
        gui: object,
        *,
        interactions_module: object,
        **kwargs: object,
    ) -> None:
        _dispatch_handler(interactions_module, handler_name)(gui, **kwargs_builder(**kwargs))

    _dispatch.__name__ = handler_name.removeprefix("_on_")
    return _dispatch


def _build_color_dispatcher(handler_name: str) -> Callable[..., None]:
    def _dispatch(
        gui: object,
        r: int,
        g: int,
        b: int,
        *,
        interactions_module: object,
        time_monotonic: Callable[[], float],
        meta: Mapping[str, object],
    ) -> None:
        _dispatch_handler(interactions_module, handler_name)(
            gui,
            r,
            g,
            b,
            **build_color_interaction_kwargs(time_monotonic=time_monotonic, meta=meta),
        )

    _dispatch.__name__ = handler_name.removeprefix("_on_")
    return _dispatch


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


dispatch_brightness_change = _build_value_dispatcher(
    "_on_reactive_brightness_change",
    build_brightness_interaction_kwargs,
)
dispatch_brightness_release = _build_release_dispatcher(
    "_on_reactive_brightness_release",
    build_brightness_interaction_kwargs,
)
dispatch_trail_change = _build_value_dispatcher(
    "_on_reactive_trail_change",
    build_trail_interaction_kwargs,
)
dispatch_trail_release = _build_release_dispatcher(
    "_on_reactive_trail_release",
    build_trail_interaction_kwargs,
)
dispatch_color_change = _build_color_dispatcher("_on_color_change")
dispatch_color_release = _build_color_dispatcher("_on_color_release")
