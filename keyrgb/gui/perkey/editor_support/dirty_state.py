"""Unified saved-snapshot and destructive-action protection for the editor."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from typing import Protocol, cast

SAVED_TEXT = "Saved"
UNSAVED_TEXT = "\u25cf Unsaved"

_UNSAVED_LABEL_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, tk.TclError)


class _UnsavedLabelProtocol(Protocol):
    def config(self, *, text: str) -> None: ...


class _UnsavedLabelOwner(Protocol):
    _unsaved_label: _UnsavedLabelProtocol


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def saved_snapshot(editor: object) -> tuple[object, ...]:
    """Capture all editor-owned state that profile actions can discard."""
    return (
        _freeze(getattr(editor, "colors", {})),
        _freeze(getattr(editor, "keymap", {})),
        _freeze(getattr(editor, "layout_tweaks", {})),
        _freeze(getattr(editor, "per_key_layout_tweaks", {})),
        _freeze(getattr(editor, "layout_slot_overrides", {})),
        _freeze(getattr(editor, "lightbar_overlay", {})),
        _freeze(getattr(editor, "secondary_lighting", None)),
        str(vars(editor).get("_physical_layout", "")),
        str(vars(editor).get("_layout_legend_pack", "")),
    )


def mark_saved(editor: object) -> None:
    vars(editor)["_saved_snapshot"] = saved_snapshot(editor)
    refresh_unsaved_indicator(editor)


def is_dirty(editor: object) -> bool:
    missing = object()
    saved = vars(editor).get("_saved_snapshot", missing)
    if saved is missing:
        return False
    return saved_snapshot(editor) != saved


def _unsaved_label_or_none(editor: object) -> _UnsavedLabelProtocol | None:
    try:
        label = cast(_UnsavedLabelOwner, editor)._unsaved_label
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    if label is None:
        return None
    return label


def refresh_unsaved_indicator(editor: object) -> None:
    """Show ``Saved`` when the snapshot matches, ``● Unsaved`` when dirty."""
    label = _unsaved_label_or_none(editor)
    if label is None:
        return
    try:
        text = UNSAVED_TEXT if is_dirty(editor) else SAVED_TEXT
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return
    try:
        label.config(text=text)
    except _UNSAVED_LABEL_ERRORS:
        return


def confirm_destructive_action(
    editor: object,
    *,
    action: str,
    save_fn: Callable[[], object] | None = None,
    ask_fn: Callable[..., object] | None = None,
) -> bool:
    """Return whether a destructive action may continue.

    ``True`` saves when the user chooses Yes, discards when choosing No, and
    cancels on Cancel/unknown responses. The callback is injectable for tests.
    """
    if not is_dirty(editor):
        return True
    if ask_fn is None:
        from tkinter import messagebox

        ask_fn = messagebox.askyesnocancel
    try:
        response = ask_fn(
            "Unsaved changes",
            f"Save changes before {action}?",
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False
    if response is None:
        return False
    if bool(response):
        if save_fn is None:
            return False
        save_fn()
        return not is_dirty(editor)
    return True


__all__ = [
    "SAVED_TEXT",
    "UNSAVED_TEXT",
    "confirm_destructive_action",
    "is_dirty",
    "mark_saved",
    "refresh_unsaved_indicator",
    "saved_snapshot",
]
