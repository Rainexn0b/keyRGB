"""Modal shell and nav-state helpers for the guided setup wizard."""

from __future__ import annotations

from typing import cast

from ..integration import SetupStep
from .wizard_shared import _WIZARD_ERRORS, TtkModule, WizardHost

_TkErrors = tuple[type[BaseException], ...]


def build_shell(host: WizardHost, *, tk_module: object, ttk_module: object) -> None:
    ttk = cast(TtkModule, ttk_module)
    host._body = ttk.Frame(host._window, padding=12)
    host._body.grid(row=0, column=0, sticky="nsew")
    host._window.columnconfigure(0, weight=1)
    host._window.rowconfigure(0, weight=1)

    host._message_label = ttk.Label(host._window, textvariable=host._message_var, wraplength=420)
    host._message_label.grid(row=1, column=0, sticky="ew", padx=12)

    nav = ttk.Frame(host._window, padding=(12, 0, 12, 12))
    nav.grid(row=2, column=0, sticky="ew")
    host._back_button = ttk.Button(nav, text="Back", command=host._on_back)
    host._back_button.grid(row=0, column=0, padx=(0, 6))
    host._next_button = ttk.Button(nav, text="Next", command=host._on_next)
    host._next_button.grid(row=0, column=1, padx=(0, 6))
    host._cancel_button = ttk.Button(nav, text="Cancel", command=host._on_close_request)
    host._cancel_button.grid(row=0, column=2, padx=(0, 6))
    host._finish_button = ttk.Button(nav, text="Finish", command=host._on_finish)
    host._finish_button.grid(row=0, column=3)


def refresh_nav_state(host: WizardHost, *, tk_errors: _TkErrors) -> None:
    child_running = host.controller.child_running
    steps = host.controller.steps
    at_first = host.controller.step_index <= 0
    at_last = host.controller.step_index >= len(steps) - 1
    state = "disabled" if child_running else "normal"
    for button in (host._back_button, host._next_button, host._cancel_button, host._finish_button):
        try:
            button.configure(state=state)
        except tk_errors:
            pass
    if not child_running:
        try:
            if at_first:
                host._back_button.configure(state="disabled")
            if at_last:
                host._next_button.configure(state="disabled")
            else:
                host._finish_button.configure(state="disabled")
            if host.controller.current_step is SetupStep.PREFLIGHT and host.controller.blocked:
                host._next_button.configure(state="disabled")
        except tk_errors:
            pass
    if host.controller.last_message and not child_running:
        host._set_message(host.controller.last_message)


def report_status(host: WizardHost, message: str) -> None:
    try:
        from keyrgb.gui.perkey.ui.status import set_status
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        return
    try:
        set_status(host.editor, message)
    except _WIZARD_ERRORS:
        pass
