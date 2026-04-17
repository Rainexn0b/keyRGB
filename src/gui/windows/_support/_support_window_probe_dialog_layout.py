#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Sequence
import tkinter as tk
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ._support_window_probe_dialogs import (
        _ConfigurableWidget,
        _DialogAction,
        _DialogButton,
        _DialogContainer,
        _DialogWidget,
        _GridPadding,
        _ProbeDialogWindow,
        _TkDialogModule,
        _TtkDialogModule,
        _WidthWidget,
    )


_PROBE_DIALOG_SCREEN_RATIO_CAP = 0.92
_PROBE_DIALOG_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


def _probe_dialog_dimensions(window: _ProbeDialogWindow, *, width: int, height: int) -> tuple[int, int]:
    try:
        root = window.root
        screen_w = int(root.winfo_screenwidth())
        screen_h = int(root.winfo_screenheight())
        max_w = max(320, int(screen_w * _PROBE_DIALOG_SCREEN_RATIO_CAP))
        max_h = max(220, int(screen_h * _PROBE_DIALOG_SCREEN_RATIO_CAP))
        return min(int(width), max_w), min(int(height), max_h)
    except _PROBE_DIALOG_ERRORS:
        return int(width), int(height)


def _dialog_wraplength(container: _WidthWidget, *, padding: int, minimum: int) -> int:
    try:
        width = int(container.winfo_width())
    except _PROBE_DIALOG_ERRORS:
        return int(minimum)
    if width <= 1:
        return int(minimum)
    return max(int(minimum), width - int(padding))


def _sync_dialog_prompt_wrap(
    label: _ConfigurableWidget,
    container: _WidthWidget,
    *,
    padding: int,
    minimum: int,
) -> None:
    try:
        label.configure(wraplength=_dialog_wraplength(container, padding=padding, minimum=minimum))
    except _PROBE_DIALOG_ERRORS:
        return


def _bind_dialog_prompt_wrap(
    dialog: _DialogWidget,
    label: _ConfigurableWidget,
    container: _DialogContainer,
    *,
    padding: int,
    minimum: int,
) -> None:
    def _sync() -> None:
        _sync_dialog_prompt_wrap(label, container, padding=padding, minimum=minimum)

    def _sync_from_event(_event: object | None = None) -> None:
        _sync()

    for widget in (dialog, container):
        try:
            widget.bind("<Configure>", _sync_from_event, add="+")
        except _PROBE_DIALOG_ERRORS:
            continue

    try:
        dialog.after(0, _sync)
    except _PROBE_DIALOG_ERRORS:
        return


def _create_probe_dialog(
    window: _ProbeDialogWindow,
    title: str,
    tk: _TkDialogModule,
    ttk: _TtkDialogModule,
    width: int,
    height: int,
    *,
    minsize: tuple[int, int],
    padding: int = 16,
    resizable: tuple[bool, bool] = (True, True),
    stretch_row: int | None = None,
) -> tuple[_DialogWidget, _DialogContainer, int, int]:
    width, height = _probe_dialog_dimensions(window, width=width, height=height)
    dialog = tk.Toplevel(window.root)
    dialog.title(title)
    dialog.transient(window.root)
    dialog.geometry(_probe_dialog_geometry(window, width=width, height=height))
    dialog.minsize(min(int(minsize[0]), width), min(int(minsize[1]), height))
    dialog.resizable(bool(resizable[0]), bool(resizable[1]))

    container = ttk.Frame(dialog, padding=padding)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    if stretch_row is not None:
        container.rowconfigure(int(stretch_row), weight=1)

    return dialog, container, width, height


def _dismiss_probe_dialog(dialog: _DialogWidget) -> None:
    try:
        dialog.grab_release()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.destroy()


def _build_dialog_button_row(
    container: object,
    *,
    ttk: _TtkDialogModule,
    row: int,
    pady: _GridPadding,
    actions: Sequence[tuple[str, _DialogAction]],
    columns: int,
) -> list[_DialogButton]:
    button_row = ttk.Frame(container)
    button_row.grid(row=row, column=0, sticky="ew", pady=pady)

    total_columns = max(1, min(int(columns), len(actions) if actions else 1))
    for column in range(total_columns):
        try:
            button_row.columnconfigure(column, weight=1)
        except _PROBE_DIALOG_ERRORS:
            continue

    created_buttons: list[_DialogButton] = []
    for index, (label, command) in enumerate(actions):
        grid_row = index // total_columns
        grid_column = index % total_columns
        button = ttk.Button(button_row, text=str(label), command=command)
        button.grid(
            row=grid_row,
            column=grid_column,
            sticky="ew",
            padx=(0 if grid_column == 0 else 8, 0),
            pady=(0 if grid_row == 0 else 8, 0),
        )
        created_buttons.append(button)

    return created_buttons


def _probe_dialog_geometry(window: _ProbeDialogWindow, *, width: int, height: int) -> str:
    try:
        root = window.root
        root.update_idletasks()
        screen_w = int(root.winfo_screenwidth())
        screen_h = int(root.winfo_screenheight())
        width, height = _probe_dialog_dimensions(window, width=width, height=height)
        root_x = int(root.winfo_rootx())
        root_y = int(root.winfo_rooty())
        root_w = max(int(root.winfo_width()), width)
        root_h = max(int(root.winfo_height()), height)
        x = root_x + max(24, (root_w - width) // 2)
        y = root_y + max(24, (root_h - height) // 3)
        x = max(0, min(screen_w - width, x))
        y = max(0, min(screen_h - height, y))
        return f"{width}x{height}+{x}+{y}"
    except _PROBE_DIALOG_ERRORS:
        return f"{width}x{height}"
