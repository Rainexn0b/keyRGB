from __future__ import annotations

import logging
from dataclasses import dataclass

from src.gui.windows import _uniform_color_bootstrap as uniform_color_bootstrap
from src.gui.windows import _uniform_color_state as uniform_color_state


@dataclass(frozen=True)
class UniformInitState:
    backend: object | None
    color_supported: bool
    device: object | None


def select_backend_best_effort(
    secondary_route,
    *,
    requested_backend: str | None,
    select_backend_fn,
    logger: logging.Logger,
):
    return uniform_color_bootstrap.select_backend_best_effort(
        secondary_route,
        requested_backend=requested_backend,
        select_backend_fn=select_backend_fn,
        logger=logger,
    )


def probe_color_support(backend, *, logger: logging.Logger) -> bool:
    return uniform_color_bootstrap.probe_color_support(backend, logger=logger)


def acquire_device_best_effort(backend, *, is_device_busy_fn, logger: logging.Logger):
    return uniform_color_bootstrap.acquire_device_best_effort(
        backend,
        is_device_busy_fn=is_device_busy_fn,
        logger=logger,
    )


def log_color_apply_failure(exc: Exception, *, debug_enabled: bool, logger: logging.Logger) -> None:
    uniform_color_state.log_color_apply_failure(exc, debug_enabled=debug_enabled, logger=logger)


def initialize_device_bootstrap_state(
    *,
    secondary_route,
    requested_backend: str | None,
    select_backend_fn,
    is_device_busy_fn,
    logger: logging.Logger,
) -> UniformInitState:
    backend = select_backend_best_effort(
        secondary_route,
        requested_backend=requested_backend,
        select_backend_fn=select_backend_fn,
        logger=logger,
    )
    color_supported = probe_color_support(backend, logger=logger)
    device = acquire_device_best_effort(backend, is_device_busy_fn=is_device_busy_fn, logger=logger)
    return UniformInitState(backend=backend, color_supported=color_supported, device=device)