from __future__ import annotations

import tkinter as tk

from . import metrics
from .contrast import contrast_ratio, meets_contrast, parse_hex_color, relative_luminance
from .detect import detect_system_prefers_dark
from .focus import INITIAL_FOCUS_DELAY_MS, schedule_initial_focus
from .ttk import (
    DARK_ACTION_FG,
    DARK_BG,
    DARK_BUTTON_ACTIVE_BG,
    DARK_BUTTON_BG,
    DARK_DESTRUCTIVE_ACTIVE_BG,
    DARK_DESTRUCTIVE_BG,
    DARK_DISABLED_FG,
    DARK_FG,
    DARK_FIELD_BG,
    DARK_FOCUS,
    DARK_PRIMARY_ACTIVE_BG,
    DARK_PRIMARY_BG,
    DISABLED_CONTRAST_TARGET,
    LIGHT_ACTION_FG,
    LIGHT_BUTTON_FALLBACK_BG,
    LIGHT_DESTRUCTIVE_ACTIVE_BG,
    LIGHT_DESTRUCTIVE_BG,
    LIGHT_DISABLED_FG,
    LIGHT_FOCUS,
    LIGHT_PRIMARY_ACTIVE_BG,
    LIGHT_PRIMARY_BG,
    NORMAL_CONTRAST_TARGET,
    TITLE_CONTRAST_TARGET,
    apply_clam_dark_theme,
    apply_clam_light_theme,
    ensure_theme_fonts,
)


def apply_clam_theme(root: tk.Misc) -> tuple[str, str]:
    """Apply a ttk theme that respects the system dark/light preference.

    This is intentionally best-effort. If we can't detect the preference, we
    keep the historical default (dark) to avoid surprising existing users.
    """

    prefers_dark = detect_system_prefers_dark()
    if prefers_dark is False:
        return apply_clam_light_theme(root)

    return apply_clam_dark_theme(root)


__all__ = [
    "DARK_ACTION_FG",
    "DARK_BG",
    "DARK_BUTTON_ACTIVE_BG",
    "DARK_BUTTON_BG",
    "DARK_DESTRUCTIVE_ACTIVE_BG",
    "DARK_DESTRUCTIVE_BG",
    "DARK_DISABLED_FG",
    "DARK_FG",
    "DARK_FIELD_BG",
    "DARK_FOCUS",
    "DARK_PRIMARY_ACTIVE_BG",
    "DARK_PRIMARY_BG",
    "DISABLED_CONTRAST_TARGET",
    "INITIAL_FOCUS_DELAY_MS",
    "LIGHT_ACTION_FG",
    "LIGHT_BUTTON_FALLBACK_BG",
    "LIGHT_DESTRUCTIVE_ACTIVE_BG",
    "LIGHT_DESTRUCTIVE_BG",
    "LIGHT_DISABLED_FG",
    "LIGHT_FOCUS",
    "LIGHT_PRIMARY_ACTIVE_BG",
    "LIGHT_PRIMARY_BG",
    "NORMAL_CONTRAST_TARGET",
    "TITLE_CONTRAST_TARGET",
    "apply_clam_dark_theme",
    "apply_clam_light_theme",
    "apply_clam_theme",
    "contrast_ratio",
    "detect_system_prefers_dark",
    "ensure_theme_fonts",
    "meets_contrast",
    "metrics",
    "parse_hex_color",
    "relative_luminance",
    "schedule_initial_focus",
]
