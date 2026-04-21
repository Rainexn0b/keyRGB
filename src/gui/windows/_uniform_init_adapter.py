from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace

from src.gui.windows import _uniform_color_bootstrap as uniform_color_bootstrap
from src.gui.windows import _uniform_color_state as uniform_color_state


@dataclass(frozen=True)
class UniformInitState:
    backend: object | None
    color_supported: bool
    device: object | None


@dataclass(frozen=True)
class UniformTargetRouteState:
    target_context: str
    requested_backend: str | None
    secondary_route: object | None
    target_is_secondary: bool
    target_label: str


def resolve_target_route_state(
    *,
    target_context: str | None,
    requested_backend: str | None,
    resolve_secondary_route_fn,
) -> UniformTargetRouteState:
    state = SimpleNamespace(
        target_context="",
        requested_backend=None,
        _secondary_route=None,
        _target_is_secondary=False,
        _target_label="Keyboard",
    )
    uniform_color_state.initialize_target_route_state(
        state,
        target_context=target_context,
        requested_backend=requested_backend,
        resolve_secondary_route_fn=resolve_secondary_route_fn,
    )
    return UniformTargetRouteState(
        target_context=str(state.target_context),
        requested_backend=state.requested_backend,
        secondary_route=state._secondary_route,
        target_is_secondary=bool(state._target_is_secondary),
        target_label=str(state._target_label),
    )


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