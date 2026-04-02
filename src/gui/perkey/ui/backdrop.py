from __future__ import annotations

from typing import Any, Callable

from tkinter import filedialog

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
        mode_var = getattr(editor, "_backdrop_mode_var", None)
        mode_combo = getattr(editor, "_backdrop_mode_combo", None)
        if mode_var is not None:
            mode_var.set("custom")
        if mode_combo is not None:
            mode_combo.set("Custom image")
        editor.canvas.reload_backdrop_image()
        set_status(editor, backdrop_updated())
    except Exception as exc:
        set_status(editor, backdrop_update_failed(exc))


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
        mode_var = getattr(editor, "_backdrop_mode_var", None)
        mode_combo = getattr(editor, "_backdrop_mode_combo", None)
        if mode_var is not None:
            mode_var.set("builtin")
        if mode_combo is not None:
            mode_combo.set("Built-in seed")
        editor.canvas.reload_backdrop_image()
        set_status(editor, backdrop_reset())
    except Exception as exc:
        set_status(editor, backdrop_reset_failed(exc))
