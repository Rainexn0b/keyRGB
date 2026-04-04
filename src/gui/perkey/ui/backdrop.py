from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Any, Callable

from src.core.profile import profiles
from src.gui.utils.profile_backdrop_storage import (
    reset_backdrop_image,
    save_backdrop_image,
)

from .status import (
    backdrop_reset,
    backdrop_reset_failed,
    backdrop_update_failed,
    backdrop_updated,
    set_status,
)


_BACKDROP_PERSISTENCE_ERRORS = (OSError, RuntimeError, ValueError)
_BACKDROP_UI_ERRORS = (AttributeError, OSError, RuntimeError, ValueError, tk.TclError)


def _sync_backdrop_mode_widgets(editor: Any, *, mode: str, label: str) -> None:
    mode_var = getattr(editor, "_backdrop_mode_var", None)
    mode_combo = getattr(editor, "_backdrop_mode_combo", None)
    if mode_var is not None:
        mode_var.set(mode)
    if mode_combo is not None:
        mode_combo.set(label)


def set_backdrop_ui(
    editor: Any,
    *,
    askopenfilename: Callable[..., str] = filedialog.askopenfilename,
    save_fn: Callable[..., None] = save_backdrop_image,
    save_mode_fn: Callable[..., None] = profiles.save_backdrop_mode,
) -> None:
    """Choose and apply a keyboard backdrop image for the current profile.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._set_backdrop`.
    """

    path = askopenfilename(
        title="Select keyboard backdrop image",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
            ("All files", "*.*"),
        ],
    )
    if not path:
        return

    try:
        save_fn(profile_name=editor.profile_name, source_path=path)
        save_mode_fn("custom", editor.profile_name)
    except _BACKDROP_PERSISTENCE_ERRORS as exc:
        set_status(editor, backdrop_update_failed(exc))
        return

    try:
        _sync_backdrop_mode_widgets(editor, mode="custom", label="Custom image")
        editor.canvas.reload_backdrop_image()
    except _BACKDROP_UI_ERRORS as exc:
        set_status(editor, backdrop_update_failed(exc))
        return

    set_status(editor, backdrop_updated())


def reset_backdrop_ui(
    editor: Any,
    *,
    reset_fn: Callable[[str], None] = reset_backdrop_image,
    save_mode_fn: Callable[..., None] = profiles.save_backdrop_mode,
) -> None:
    """Reset the keyboard backdrop image for the current profile.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._reset_backdrop`.
    """

    try:
        reset_fn(editor.profile_name)
        save_mode_fn("builtin", editor.profile_name)
    except _BACKDROP_PERSISTENCE_ERRORS as exc:
        set_status(editor, backdrop_reset_failed(exc))
        return

    try:
        _sync_backdrop_mode_widgets(editor, mode="builtin", label="Built-in seed")
        editor.canvas.reload_backdrop_image()
    except _BACKDROP_UI_ERRORS as exc:
        set_status(editor, backdrop_reset_failed(exc))
        return

    set_status(editor, backdrop_reset())
