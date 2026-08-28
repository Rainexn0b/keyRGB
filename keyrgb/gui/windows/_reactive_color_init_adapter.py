from __future__ import annotations

from dataclasses import dataclass

from keyrgb.core.backends.registry import select_backend
from keyrgb.core.config import Config
from keyrgb.gui.theme import apply_clam_theme
from keyrgb.gui.utils.window_geometry import compute_centered_window_geometry
from keyrgb.gui.utils.window_icon import apply_keyrgb_window_icon
from keyrgb.gui.widgets.color_wheel import ColorWheel
from keyrgb.gui.windows import _reactive_color_bootstrap as reactive_color_bootstrap


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


__all__ = [
    "ColorWheel",
    "Config",
    "ReactiveColorInitState",
    "apply_clam_theme",
    "apply_keyrgb_window_icon",
    "compute_centered_window_geometry",
    "initialize_runtime_state",
    "reactive_color_bootstrap",
    "select_backend",
]
