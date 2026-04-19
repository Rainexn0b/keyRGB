from __future__ import annotations

import logging

from src.core.backends.registry import select_backend
from src.core.config import Config
from src.gui.theme import apply_clam_theme
from src.gui.utils.window_geometry import compute_centered_window_geometry
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.widgets.color_wheel import ColorWheel
from src.gui.windows import (
    _reactive_color_bootstrap as reactive_color_bootstrap,
    _reactive_color_interactions as reactive_color_interactions,
    _reactive_color_state as _reactive_color_state,
    _reactive_color_ui as reactive_color_ui,
)


def commit_brightness_to_config(
    config: object,
    brightness_percent: float | int | None,
    *,
    logger: logging.Logger,
) -> int | None:
    return _reactive_color_state.commit_brightness_to_config(
        config,
        brightness_percent,
        logger=logger,
    )


def commit_color_to_config(
    config: object,
    use_manual_var: object,
    color: tuple[int, int, int],
    *,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    _reactive_color_state.commit_color_to_config(
        config,
        use_manual_var,
        color,
        tk_error=tk_error,
        logger=logger,
    )


def commit_trail_to_config(
    config: object,
    trail_percent: float | int | None,
    *,
    logger: logging.Logger,
) -> int | None:
    return _reactive_color_state.commit_trail_to_config(
        config,
        trail_percent,
        logger=logger,
    )


def read_reactive_brightness_percent(config: object, *, logger: logging.Logger) -> int | None:
    return _reactive_color_state.read_reactive_brightness_percent(config, logger=logger)


def read_reactive_trail_percent(config: object, *, logger: logging.Logger) -> int | None:
    return _reactive_color_state.read_reactive_trail_percent(config, logger=logger)


def sync_color_wheel_brightness(
    color_wheel: object,
    use_manual_var: object,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    _reactive_color_state.sync_color_wheel_brightness(
        color_wheel,
        use_manual_var,
        percent=percent,
        tk_error=tk_error,
        logger=logger,
    )


def sync_reactive_brightness_widgets(
    brightness_var: object,
    brightness_label: object,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    _reactive_color_state.sync_reactive_brightness_widgets(
        brightness_var,
        brightness_label,
        percent=percent,
        tk_error=tk_error,
        logger=logger,
    )


def sync_reactive_trail_widgets(
    trail_var: object,
    trail_label: object,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    _reactive_color_state.sync_reactive_trail_widgets(
        trail_var,
        trail_label,
        percent=percent,
        tk_error=tk_error,
        logger=logger,
    )


__all__ = [
    "ColorWheel",
    "Config",
    "apply_clam_theme",
    "apply_keyrgb_window_icon",
    "commit_brightness_to_config",
    "commit_color_to_config",
    "commit_trail_to_config",
    "compute_centered_window_geometry",
    "reactive_color_bootstrap",
    "reactive_color_interactions",
    "reactive_color_ui",
    "read_reactive_brightness_percent",
    "read_reactive_trail_percent",
    "select_backend",
    "sync_color_wheel_brightness",
    "sync_reactive_brightness_widgets",
    "sync_reactive_trail_widgets",
]
