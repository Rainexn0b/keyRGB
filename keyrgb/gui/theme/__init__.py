from __future__ import annotations

import tkinter as tk

from .detect import detect_system_prefers_dark
from .ttk import apply_clam_dark_theme, apply_clam_light_theme


def apply_clam_theme(
    root: tk.Misc,
    *,
    include_checkbuttons: bool = False,
    map_checkbutton_state: bool = False,
) -> tuple[str, str]:
    """Apply a ttk theme that respects the system dark/light preference.

    This is intentionally best-effort. If we can't detect the preference, we
    keep the historical default (dark) to avoid surprising existing users.
    """

    prefers_dark = detect_system_prefers_dark()
    if prefers_dark is False:
        return apply_clam_light_theme(
            root,
            include_checkbuttons=include_checkbuttons,
            map_checkbutton_state=map_checkbutton_state,
        )

    return apply_clam_dark_theme(
        root,
        include_checkbuttons=include_checkbuttons,
        map_checkbutton_state=map_checkbutton_state,
    )


__all__ = [
    "apply_clam_dark_theme",
    "apply_clam_light_theme",
    "apply_clam_theme",
    "detect_system_prefers_dark",
]
