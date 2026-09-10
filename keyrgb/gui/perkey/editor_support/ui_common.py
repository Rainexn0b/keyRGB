from __future__ import annotations

from tkinter import TclError

_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}

_STATUS_WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, TclError, TypeError, ValueError)
_TK_CALLBACK_SETUP_ERRORS = (RuntimeError, TclError)


def _set_backdrop_mode_from_label(editor, label: str) -> None:
    for mode, mode_label in _BACKDROP_MODE_LABELS.items():
        if mode_label == label:
            editor._backdrop_mode_var.set(mode)
            break
    else:
        editor._backdrop_mode_var.set("builtin")
    editor._on_backdrop_mode_changed()
