#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, TypeAlias, TypeVar

from . import _support_window_probe_dialog_layout as _dialog_layout


_GridPadding: TypeAlias = tuple[int, int]
_DialogAction: TypeAlias = Callable[[], None]
_DialogBindCallback: TypeAlias = Callable[[object | None], None]
_ChoiceValueT = TypeVar("_ChoiceValueT")


class _ProbeDialogRoot(Protocol):
    def update_idletasks(self) -> None: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...

    def winfo_rootx(self) -> int: ...

    def winfo_rooty(self) -> int: ...

    def winfo_width(self) -> int: ...

    def winfo_height(self) -> int: ...


class _ProbeDialogWindow(Protocol):
    root: _ProbeDialogRoot


class _ThemedProbeDialogWindow(_ProbeDialogWindow, Protocol):
    _bg_color: str
    _fg_color: str


class _WidthWidget(Protocol):
    def winfo_width(self) -> int: ...


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _FocusableWidget(Protocol):
    def focus_set(self) -> None: ...


class _GridWidget(Protocol):
    def grid(
        self,
        *,
        row: int,
        column: int,
        sticky: str,
        padx: _GridPadding | None = None,
        pady: _GridPadding | None = None,
    ) -> None: ...


class _BindableWidget(Protocol):
    def bind(self, sequence: str, callback: _DialogBindCallback, add: str | None = None) -> None: ...


class _DialogContainer(_WidthWidget, _BindableWidget, Protocol):
    def pack(self, *, fill: str, expand: bool = False) -> None: ...

    def columnconfigure(self, index: int, weight: int = 0) -> None: ...

    def rowconfigure(self, index: int, weight: int = 0) -> None: ...


class _DialogButton(_GridWidget, _FocusableWidget, Protocol):
    pass


class _DialogLabel(_GridWidget, _ConfigurableWidget, Protocol):
    pass


class _DialogTextWidget(_GridWidget, _FocusableWidget, _ConfigurableWidget, Protocol):
    def insert(self, index: str, value: str) -> None: ...

    def get(self, start: str, end: str) -> str: ...


class _DialogWidget(_BindableWidget, Protocol):
    def title(self, value: str) -> None: ...

    def transient(self, parent: object) -> None: ...

    def geometry(self, value: str) -> None: ...

    def minsize(self, width: int, height: int) -> None: ...

    def resizable(self, width: bool, height: bool) -> None: ...

    def protocol(self, name: str, callback: _DialogAction) -> None: ...

    def after(self, delay_ms: int, callback: _DialogAction) -> None: ...

    def grab_set(self) -> None: ...

    def grab_release(self) -> None: ...

    def destroy(self) -> None: ...

    def wait_window(self) -> None: ...


class _FrameFactory(Protocol):
    def __call__(self, parent: object, *, padding: int | None = None) -> _DialogContainer: ...


class _ButtonFactory(Protocol):
    def __call__(self, parent: object, *, text: str, command: _DialogAction) -> _DialogButton: ...


class _LabelFactory(Protocol):
    def __call__(self, parent: object, *, text: str, justify: str, wraplength: int) -> _DialogLabel: ...


class _ScrolledTextFactory(Protocol):
    def __call__(
        self,
        parent: object,
        *,
        wrap: str,
        height: int,
        background: str,
        foreground: str,
        insertbackground: str,
    ) -> _DialogTextWidget: ...


class _ToplevelFactory(Protocol):
    def __call__(self, parent: object) -> _DialogWidget: ...


class _TtkDialogModule(Protocol):
    Frame: _FrameFactory
    Button: _ButtonFactory
    Label: _LabelFactory


class _TkDialogModule(Protocol):
    Toplevel: _ToplevelFactory


class _ScrolledTextModule(Protocol):
    ScrolledText: _ScrolledTextFactory


_PROBE_DIALOG_SCREEN_RATIO_CAP = _dialog_layout._PROBE_DIALOG_SCREEN_RATIO_CAP
_PROBE_DIALOG_ERRORS = _dialog_layout._PROBE_DIALOG_ERRORS
_probe_dialog_dimensions = _dialog_layout._probe_dialog_dimensions
_dialog_wraplength = _dialog_layout._dialog_wraplength
_sync_dialog_prompt_wrap = _dialog_layout._sync_dialog_prompt_wrap
_bind_dialog_prompt_wrap = _dialog_layout._bind_dialog_prompt_wrap
_build_dialog_button_row = _dialog_layout._build_dialog_button_row
_probe_dialog_geometry = _dialog_layout._probe_dialog_geometry


def _show_probe_message_dialog(
    window: _ThemedProbeDialogWindow,
    *,
    title: str,
    message: str,
    tk: _TkDialogModule,
    ttk: _TtkDialogModule,
    scrolledtext: _ScrolledTextModule,
    width: int = 720,
    height: int = 560,
) -> bool:
    dialog, container, _, _ = _dialog_layout._create_probe_dialog(
        window, title, tk, ttk, width, height, minsize=(560, 360), padding=14, stretch_row=0
    )

    body = scrolledtext.ScrolledText(
        container,
        wrap="word",
        height=18,
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    body.grid(row=0, column=0, sticky="nsew")
    body.insert("1.0", str(message or ""))
    body.configure(state="disabled")

    confirmed = False

    def close(*, ok: bool) -> None:
        nonlocal confirmed
        confirmed = bool(ok)
        _dialog_layout._dismiss_probe_dialog(dialog)

    created_buttons = _build_dialog_button_row(
        container,
        ttk=ttk,
        row=1,
        pady=(12, 0),
        actions=[("OK", lambda: close(ok=True))],
        columns=1,
    )
    ok_btn = created_buttons[0]

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(ok=False))
    try:
        dialog.grab_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    try:
        ok_btn.focus_set()
        body.focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return confirmed


def _ask_probe_choice_dialog(
    window: _ProbeDialogWindow,
    *,
    title: str,
    prompt: str,
    tk: _TkDialogModule,
    ttk: _TtkDialogModule,
    choices: Sequence[tuple[str, _ChoiceValueT]],
    width: int = 520,
    height: int = 240,
) -> _ChoiceValueT | None:
    dialog, container, width, _ = _dialog_layout._create_probe_dialog(
        window, title, tk, ttk, width, height, minsize=(420, 200), resizable=(True, False)
    )

    prompt_label = ttk.Label(container, text=str(prompt or ""), justify="left", wraplength=width - 72)
    prompt_label.grid(row=0, column=0, sticky="w")
    _bind_dialog_prompt_wrap(dialog, prompt_label, container, padding=72, minimum=220)

    selected_value: _ChoiceValueT | None = None

    def close(value: _ChoiceValueT | None) -> None:
        nonlocal selected_value
        selected_value = value
        _dialog_layout._dismiss_probe_dialog(dialog)

    def _close_with(value: _ChoiceValueT) -> _DialogAction:
        return lambda: close(value)

    created_buttons = _build_dialog_button_row(
        container,
        ttk=ttk,
        row=1,
        pady=(18, 0),
        actions=[(str(label), _close_with(value)) for label, value in choices],
        columns=2,
    )

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(None))
    try:
        dialog.grab_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    try:
        if created_buttons:
            created_buttons[0].focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return selected_value


def _ask_probe_notes_dialog(
    window: _ThemedProbeDialogWindow,
    *,
    title: str,
    prompt: str,
    tk: _TkDialogModule,
    ttk: _TtkDialogModule,
    scrolledtext: _ScrolledTextModule,
    width: int = 720,
    height: int = 340,
) -> str | None:
    dialog, container, width, _ = _dialog_layout._create_probe_dialog(
        window, title, tk, ttk, width, height, minsize=(560, 260), stretch_row=1
    )

    prompt_label = ttk.Label(container, text=str(prompt or ""), justify="left", wraplength=width - 72)
    prompt_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
    _bind_dialog_prompt_wrap(dialog, prompt_label, container, padding=72, minimum=240)

    notes_box = scrolledtext.ScrolledText(
        container,
        wrap="word",
        height=10,
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    notes_box.grid(row=1, column=0, sticky="nsew")

    notes_value: str | None = None

    def close(*, ok: bool) -> None:
        nonlocal notes_value
        if ok:
            notes_value = str(notes_box.get("1.0", "end")).strip()
        _dialog_layout._dismiss_probe_dialog(dialog)

    _build_dialog_button_row(
        container,
        ttk=ttk,
        row=2,
        pady=(12, 0),
        actions=[("OK", lambda: close(ok=True)), ("Cancel", lambda: close(ok=False))],
        columns=2,
    )

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(ok=False))
    try:
        dialog.grab_set()
        notes_box.focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return notes_value
