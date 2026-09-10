from __future__ import annotations

from collections.abc import Sequence

from . import _support_window_probe_dialog_layout as _dialog_layout, _support_window_probe_dialog_types as _dialog_types
from ._support_window_probe_dialog_types import _ChoiceValueT

_GridPadding = _dialog_types._GridPadding
_DialogAction = _dialog_types._DialogAction
_DialogBindCallback = _dialog_types._DialogBindCallback
_ProbeDialogRoot = _dialog_types._ProbeDialogRoot
_ProbeDialogWindow = _dialog_types._ProbeDialogWindow
_ThemedProbeDialogWindow = _dialog_types._ThemedProbeDialogWindow
_WidthWidget = _dialog_types._WidthWidget
_ConfigurableWidget = _dialog_types._ConfigurableWidget
_FocusableWidget = _dialog_types._FocusableWidget
_GridWidget = _dialog_types._GridWidget
_BindableWidget = _dialog_types._BindableWidget
_DialogContainer = _dialog_types._DialogContainer
_DialogButton = _dialog_types._DialogButton
_DialogLabel = _dialog_types._DialogLabel
_DialogTextWidget = _dialog_types._DialogTextWidget
_DialogWidget = _dialog_types._DialogWidget
_FrameFactory = _dialog_types._FrameFactory
_ButtonFactory = _dialog_types._ButtonFactory
_LabelFactory = _dialog_types._LabelFactory
_ScrolledTextFactory = _dialog_types._ScrolledTextFactory
_ToplevelFactory = _dialog_types._ToplevelFactory
_TtkDialogModule = _dialog_types._TtkDialogModule
_TkDialogModule = _dialog_types._TkDialogModule
_ScrolledTextModule = _dialog_types._ScrolledTextModule


_PROBE_DIALOG_SCREEN_RATIO_CAP = _dialog_layout._PROBE_DIALOG_SCREEN_RATIO_CAP
_PROBE_DIALOG_ERRORS = _dialog_layout._PROBE_DIALOG_ERRORS
_probe_dialog_dimensions = _dialog_layout._probe_dialog_dimensions
_dialog_wraplength = _dialog_layout._dialog_wraplength
_sync_dialog_prompt_wrap = _dialog_layout._sync_dialog_prompt_wrap
_bind_dialog_prompt_wrap = _dialog_layout._bind_dialog_prompt_wrap
_build_dialog_button_row = _dialog_layout._build_dialog_button_row
_probe_dialog_geometry = _dialog_layout._probe_dialog_geometry


def _bind_probe_dialog_keys(
    dialog: _BindableWidget,
    bindings: Sequence[tuple[str, _DialogBindCallback]],
) -> None:
    """Bind dialog shortcut keys additively without bypassing close routes."""
    for sequence, handler in bindings:
        dialog.bind(sequence, handler, add="+")


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
    closed = False

    def close(*, ok: bool) -> None:
        nonlocal closed, confirmed
        if closed:
            return
        closed = True
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

    def _on_escape(_event: object | None = None) -> str:
        close(ok=False)
        return "break"

    def _on_confirm(_event: object | None = None) -> str:
        close(ok=True)
        return "break"

    _bind_probe_dialog_keys(
        dialog,
        [
            ("<Escape>", _on_escape),
            ("<Return>", _on_confirm),
            ("<KP_Enter>", _on_confirm),
        ],
    )
    try:
        dialog.grab_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    try:
        ok_btn.focus_set()
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
    closed = False

    def close(value: _ChoiceValueT | None) -> None:
        nonlocal closed, selected_value
        if closed:
            return
        closed = True
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

    def _on_escape(_event: object | None = None) -> str:
        close(None)
        return "break"

    def _on_confirm_default(_event: object | None = None) -> str:
        if choices:
            focused = dialog.focus_get()
            for button, (_label, value) in zip(created_buttons, choices, strict=False):
                if focused is button:
                    close(value)
                    break
            else:
                close(choices[0][1])
        return "break"

    _bind_probe_dialog_keys(
        dialog,
        [
            ("<Escape>", _on_escape),
            ("<Return>", _on_confirm_default),
            ("<KP_Enter>", _on_confirm_default),
        ],
    )
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
    closed = False

    def close(*, ok: bool) -> None:
        nonlocal closed, notes_value
        if closed:
            return
        closed = True
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

    def _on_escape(_event: object | None = None) -> str:
        close(ok=False)
        return "break"

    # NOTE: no bare <Return>/<KP_Enter> binding here: the ScrolledText
    # notes box needs newline keys, so only the existing OK/Cancel
    # buttons confirm or cancel.
    _bind_probe_dialog_keys(dialog, [("<Escape>", _on_escape)])
    try:
        dialog.grab_set()
        notes_box.focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return notes_value
