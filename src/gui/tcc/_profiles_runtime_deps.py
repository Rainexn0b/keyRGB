"""Grouped runtime dependency seam for the TCC profiles window facade."""

from __future__ import annotations

import tkinter as _tk
from tkinter import messagebox as _messagebox
from tkinter import ttk as _ttk

from src.core.power.tcc_profiles.models import is_builtin_profile_id
from src.core.utils.logging_utils import log_throttled
from src.gui.theme import apply_clam_theme
from src.gui.utils.window_geometry import compute_centered_window_geometry
from src.gui.utils.window_icon import apply_keyrgb_window_icon

from ._profile_actions import create_profile, delete_profile, duplicate_profile, edit_profile, rename_profile
from ._profiles_window_ui import build_profiles_window


class TccProfilesRuntimeDeps:
    tk = _tk
    ttk = _ttk
    messagebox = _messagebox
    log_throttled = log_throttled
    is_builtin_profile_id = is_builtin_profile_id
    apply_keyrgb_window_icon = apply_keyrgb_window_icon
    apply_clam_theme = apply_clam_theme
    compute_centered_window_geometry = compute_centered_window_geometry
    build_profiles_window = build_profiles_window
    create_profile = create_profile
    delete_profile = delete_profile
    duplicate_profile = duplicate_profile
    edit_profile = edit_profile
    rename_profile = rename_profile
