from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Protocol, Sequence, cast

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
_BACKDROP_FILE_TYPES: tuple[tuple[str, str], ...] = (
    ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
    ("All files", "*.*"),
)


class _SettableProtocol(Protocol):
    def set(self, value: str) -> None: ...


class _BackdropCanvasProtocol(Protocol):
    def reload_backdrop_image(self) -> None: ...


class _BackdropEditorProtocol(Protocol):
    profile_name: str
    canvas: _BackdropCanvasProtocol


class _BackdropModeVarOwner(Protocol):
    _backdrop_mode_var: _SettableProtocol


class _BackdropModeComboOwner(Protocol):
    _backdrop_mode_combo: _SettableProtocol


class _AskOpenFilenameProtocol(Protocol):
    def __call__(self, *, title: str, filetypes: Sequence[tuple[str, str]]) -> str: ...


class _SaveBackdropImageProtocol(Protocol):
    def __call__(self, *, profile_name: str, source_path: str) -> None: ...


class _SaveBackdropModeProtocol(Protocol):
    def __call__(self, mode: str, profile_name: str) -> None: ...


class _ResetBackdropImageProtocol(Protocol):
    def __call__(self, profile_name: str) -> None: ...


def _backdrop_mode_var_or_none(editor: object) -> _SettableProtocol | None:
    try:
        return cast(_BackdropModeVarOwner, editor)._backdrop_mode_var
    except AttributeError:
        return None


def _backdrop_mode_combo_or_none(editor: object) -> _SettableProtocol | None:
    try:
        return cast(_BackdropModeComboOwner, editor)._backdrop_mode_combo
    except AttributeError:
        return None


def _sync_backdrop_mode_widgets(editor: object, *, mode: str, label: str) -> None:
    mode_var = _backdrop_mode_var_or_none(editor)
    mode_combo = _backdrop_mode_combo_or_none(editor)
    if mode_var is not None:
        mode_var.set(mode)
    if mode_combo is not None:
        mode_combo.set(label)


def set_backdrop_ui(
    editor: _BackdropEditorProtocol,
    *,
    askopenfilename: _AskOpenFilenameProtocol = filedialog.askopenfilename,
    save_fn: _SaveBackdropImageProtocol = save_backdrop_image,
    save_mode_fn: _SaveBackdropModeProtocol = profiles.save_backdrop_mode,
) -> None:
    """Choose and apply a keyboard backdrop image for the current profile.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._set_backdrop`.
    """

    path = askopenfilename(
        title="Select keyboard backdrop image",
        filetypes=_BACKDROP_FILE_TYPES,
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
    editor: _BackdropEditorProtocol,
    *,
    reset_fn: _ResetBackdropImageProtocol = reset_backdrop_image,
    save_mode_fn: _SaveBackdropModeProtocol = profiles.save_backdrop_mode,
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
