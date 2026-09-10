"""Shared protocols and constants for the guided setup wizard Tk layer."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import Protocol

from ..integration import GuidedSetupController
from ..model import SetupDraft
from ..preflight import CalibrationPreflightResult

_TK_ERRORS = (RuntimeError, tk.TclError)
_WIZARD_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_CALIBRATOR_POLL_MS = 250

_OVERLAY_FIELDS: tuple[tuple[str, str], ...] = (
    ("dx", "Horizontal shift (dx)"),
    ("dy", "Vertical shift (dy)"),
    ("sx", "Horizontal scale (sx)"),
    ("sy", "Vertical scale (sy)"),
    ("inset", "Edge inset (0.00-0.20)"),
)
_OVERLAY_DEFAULTS: dict[str, float] = {
    "dx": 0.0,
    "dy": 0.0,
    "sx": 1.0,
    "sy": 1.0,
    "inset": 0.06,
}


class ChildProcessProtocol(Protocol):
    def poll(self) -> int | None: ...


class WizardRootProtocol(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], None]) -> object: ...

    def after_cancel(self, after_id: object) -> None: ...


class TkModule(Protocol):
    """Factory surface of ``tkinter`` used by the wizard page renderers."""

    def BooleanVar(self, **kwargs: object) -> tk.BooleanVar: ...


class TtkModule(Protocol):
    """Factory surface of ``tkinter.ttk`` used by the wizard shell and pages."""

    def Frame(self, parent: object, **kwargs: object) -> ttk.Frame: ...

    def Label(self, parent: object, **kwargs: object) -> ttk.Label: ...

    def Button(self, parent: object, **kwargs: object) -> ttk.Button: ...

    def Combobox(self, parent: object, **kwargs: object) -> ttk.Combobox: ...

    def Checkbutton(self, parent: object, **kwargs: object) -> ttk.Checkbutton: ...

    def Entry(self, parent: object, **kwargs: object) -> ttk.Entry: ...


class GuidedSessionFactory(Protocol):
    """Create a temp guided session file (keyword ``rows``/``cols``)."""

    def __call__(self, draft: SetupDraft, *, rows: int, cols: int) -> Path: ...


PreflightResolver = Callable[[object], CalibrationPreflightResult]
"""Re-resolve setup preflight for an editor object."""

SessionCleaner = Callable[[Path | None], None]
"""Remove a temp guided session file (tolerates ``None``)."""

GuidedResultAdopter = Callable[[GuidedSetupController, Path | None], tuple[bool, str]]
"""Adopt a finished calibrator result into the controller draft."""

SlotStatesFactory = Callable[[SetupDraft], list[object]]
"""List optional slot states for a draft."""


class WizardHost(Protocol):
    """Structural surface of ``GuidedSetupWizard`` used by part helpers."""

    editor: object
    controller: GuidedSetupController
    _window: tk.Toplevel
    _message_var: tk.StringVar
    _body: ttk.Frame
    _message_label: ttk.Label
    _back_button: ttk.Button
    _next_button: ttk.Button
    _cancel_button: ttk.Button
    _finish_button: ttk.Button
    _overlay_entries: dict[str, ttk.Entry]
    _option_vars: dict[str, tk.BooleanVar]
    _option_labels: dict[str, ttk.Entry]
    _child_process: ChildProcessProtocol | None

    def _set_message(self, text: str) -> None: ...

    def _render(self) -> None: ...

    def _refresh_nav(self) -> None: ...

    def _retry_preflight(self) -> None: ...

    def _harvest_optional_keys(self) -> None: ...

    def _harvest_overlay(self) -> None: ...

    def _on_launch_calibrator(self) -> None: ...

    def _on_back(self) -> None: ...

    def _on_next(self) -> None: ...

    def _on_close_request(self) -> None: ...

    def _on_finish(self) -> None: ...

    def _poll_child(self) -> None: ...

    def _finish_child(self) -> None: ...

    def _after(self, delay_ms: int, callback: Callable[[], None]) -> None: ...

    def _stop_polling(self) -> None: ...
