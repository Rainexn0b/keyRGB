from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReactiveColorInitState:
    color_supported: bool


def initialize_runtime_state(*, select_backend_fn, probe_color_support_fn, logger) -> ReactiveColorInitState:
    return ReactiveColorInitState(
        color_supported=bool(
            probe_color_support_fn(
                select_backend_fn=select_backend_fn,
                logger=logger,
            )
        )
    )
