from __future__ import annotations
from typing import Any

import logging


def read_reactive_brightness_percent(config: Any, *, logger: logging.Logger) -> int | None:
    raw = getattr(config, "reactive_brightness", getattr(config, "brightness", 0))
    try:
        hw = int(raw or 0)
    except (TypeError, ValueError):
        logger.debug(
            "Invalid persisted reactive brightness %r; leaving reactive brightness widgets unchanged",
            raw,
            exc_info=True,
        )
        return None
    return max(0, min(100, int(round(hw * 2))))


def sync_reactive_brightness_widgets(
    brightness_var: Any,
    brightness_label: Any,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    if percent is None:
        return
    try:
        brightness_var.set(float(percent))
        brightness_label.config(text=f"{percent}%")
    except tk_error:
        logger.debug("Reactive brightness widgets were unavailable during initialization", exc_info=True)


def sync_color_wheel_brightness(
    color_wheel: Any,
    use_manual_var: Any,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    if color_wheel is None:
        return
    if bool(use_manual_var.get()):
        return
    if percent is None:
        return
    try:
        color_wheel.set_brightness_percent(percent)
    except tk_error:
        logger.debug("Reactive color wheel was unavailable during brightness sync", exc_info=True)


def commit_color_to_config(
    config: Any,
    use_manual_var: Any,
    color: tuple[int, int, int],
    *,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    try:
        setattr(config, "reactive_use_manual_color", True)
        use_manual_var.set(True)
        setattr(config, "reactive_color", color)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError, tk_error):
        logger.debug("Failed to save reactive_color", exc_info=True)


def commit_brightness_to_config(
    config: Any, brightness_percent: float | int | None, *, logger: logging.Logger
) -> int | None:
    if brightness_percent is None:
        return None
    try:
        pct = float(brightness_percent)
    except (TypeError, ValueError):
        return None

    pct = max(0.0, min(100.0, pct))
    hw = int(round(pct / 2.0))
    try:
        setattr(config, "reactive_brightness", hw)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        logger.debug("Failed to save brightness", exc_info=True)
        return None
    return hw


def read_reactive_trail_percent(config: Any, *, logger: logging.Logger) -> int | None:
    raw = getattr(config, "reactive_trail_percent", 50)
    try:
        pct = int(raw or 50)
    except (TypeError, ValueError):
        logger.debug(
            "Invalid persisted reactive_trail_percent %r; leaving trail widgets unchanged",
            raw,
            exc_info=True,
        )
        return None
    return max(1, min(100, pct))


def sync_reactive_trail_widgets(
    trail_var: Any,
    trail_label: Any,
    *,
    percent: int | None,
    tk_error: type[BaseException],
    logger: logging.Logger,
) -> None:
    if percent is None:
        return
    try:
        trail_var.set(float(percent))
        trail_label.config(text=f"{percent}%")
    except tk_error:
        logger.debug("Reactive trail widgets were unavailable during initialization", exc_info=True)


def commit_trail_to_config(
    config: Any, trail_percent: float | int | None, *, logger: logging.Logger
) -> int | None:
    if trail_percent is None:
        return None
    try:
        pct = float(trail_percent)
    except (TypeError, ValueError):
        return None

    pct = max(1.0, min(100.0, pct))
    hw = int(round(pct))
    try:
        setattr(config, "reactive_trail_percent", hw)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        logger.debug("Failed to save reactive trail percent", exc_info=True)
        return None
    return hw
