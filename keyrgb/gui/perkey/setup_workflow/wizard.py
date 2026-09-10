"""UX-04 modal guided setup wizard (thin Tk layer)."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Mapping
from tkinter import ttk
from typing import cast

from .integration import (
    GuidedSetupController,
    SetupStep,
    adopt_guided_result,
    build_setup_commit_callbacks,
    capture_setup_source,
    cleanup_guided_session,
    create_guided_session_file,
    optional_slot_states,
    resolve_setup_preflight,
)
from .model import draft_from_source
from .wizard_parts import wizard_pages as pages
from .wizard_parts.wizard_pages import _layout_labels
from .wizard_parts.wizard_shared import (
    _OVERLAY_DEFAULTS,
    _OVERLAY_FIELDS,
    _TK_ERRORS,
    _WIZARD_ERRORS,
    ChildProcessProtocol,
    WizardRootProtocol,
)

__all__ = ["GuidedSetupWizard", "open_guided_setup"]

logger = logging.getLogger(__name__)

WIZARD_ATTR = "_guided_setup_wizard"


def open_guided_setup(
    editor: object,
    *,
    dialog_class: type[GuidedSetupWizard] | None = None,
    launcher: Callable[[object], object] | None = None,
    env: Mapping[str, str] | None = None,
    hardware_module: object | None = None,
) -> object:
    """Open (or focus) the modal guided setup wizard for *editor*.

    Never blocks: the dialog is modeless-from-Tk's perspective with a local
    grab, and no ``wait_window`` is used here.
    """

    existing = getattr(editor, WIZARD_ATTR, None)
    if existing is not None:
        try:
            if bool(existing.is_alive()):
                existing.focus()
                return existing
        except _WIZARD_ERRORS:
            pass
        try:
            delattr(editor, WIZARD_ATTR)
        except _WIZARD_ERRORS:
            pass
    source = capture_setup_source(editor)
    draft = draft_from_source(source)
    preflight = resolve_setup_preflight(editor, env=env, hardware_module=hardware_module)
    controller = GuidedSetupController(
        draft=draft,
        preflight=preflight,
        rows=preflight.rows,
        cols=preflight.cols,
    )
    dialog_cls = dialog_class if dialog_class is not None else GuidedSetupWizard
    dialog = dialog_cls(editor, controller, launcher=launcher)
    try:
        setattr(editor, WIZARD_ATTR, dialog)
    except _WIZARD_ERRORS:
        pass
    return dialog


class GuidedSetupWizard:
    """Thin Tk modal rendering a :class:`GuidedSetupController`."""

    def __init__(
        self,
        editor: object,
        controller: GuidedSetupController,
        *,
        launcher: Callable[[object], object] | None = None,
    ) -> None:
        self.editor = editor
        self.controller = controller
        self._launcher = launcher
        self._child_process: ChildProcessProtocol | None = None
        self._poll_job: object | None = None
        self._overlay_entries: dict[str, ttk.Entry] = {}
        self._option_vars: dict[str, tk.BooleanVar] = {}
        self._option_labels: dict[str, ttk.Entry] = {}
        # Built by build_shell(); declared here so the type gate sees them.
        self._body: ttk.Frame
        self._message_label: ttk.Label
        self._back_button: ttk.Button
        self._next_button: ttk.Button
        self._cancel_button: ttk.Button
        self._finish_button: ttk.Button

        root = getattr(editor, "root", None)
        self._window = tk.Toplevel(root)
        self._window.title("KeyRGB - Guided Keyboard Setup")
        try:
            self._window.transient(root)
        except _TK_ERRORS:
            pass
        try:
            self._window.protocol("WM_DELETE_WINDOW", self._on_close_request)
        except _TK_ERRORS:
            pass

        self._message_var = tk.StringVar(value="")
        self._build_shell()
        self._render()
        try:
            self._window.grab_set()
        except _TK_ERRORS:
            pass

    # -- lifetime ------------------------------------------------------
    def is_alive(self) -> bool:
        try:
            return bool(self._window.winfo_exists())
        except _TK_ERRORS:
            return False

    def focus(self) -> None:
        try:
            self._window.lift()
            self._window.focus_force()
        except _TK_ERRORS:
            pass

    def _release(self) -> None:
        try:
            self._window.grab_release()
        except _TK_ERRORS:
            pass
        try:
            delattr(self.editor, WIZARD_ATTR)
        except _WIZARD_ERRORS:
            pass

    def _destroy(self) -> None:
        self._stop_polling()
        self._release()
        try:
            self._window.destroy()
        except _TK_ERRORS:
            pass

    # -- shell ---------------------------------------------------------
    def _build_shell(self) -> None:
        from .wizard_parts.wizard_shell import build_shell

        build_shell(self, tk_module=tk, ttk_module=ttk)

    def _set_message(self, text: str) -> None:
        try:
            self._message_var.set(text)
        except _TK_ERRORS:
            pass

    def _editor_root(self) -> WizardRootProtocol:
        root = getattr(self.editor, "root", self._window)
        return cast(WizardRootProtocol, root)

    def _after(self, delay_ms: int, callback: Callable[[], None]) -> None:
        root = self._editor_root()
        try:
            self._poll_job = root.after(delay_ms, callback)
        except _TK_ERRORS as exc:
            logger.debug("guided setup wizard cannot schedule poll: %s", exc)

    def _stop_polling(self) -> None:
        job, self._poll_job = self._poll_job, None
        if job is None:
            return
        try:
            self._editor_root().after_cancel(job)
        except _TK_ERRORS:
            pass

    # -- navigation ----------------------------------------------------
    def _on_back(self) -> None:
        self._harvest_page()
        self.controller.go_back()
        self._render()

    def _on_next(self) -> None:
        self._harvest_page()
        self.controller.go_next()
        self._render()

    def _on_close_request(self) -> None:
        allowed, message = self.controller.close_allowed()
        if not allowed:
            self._set_message(message)
            self._safe_status(message)
            return
        self._cleanup_session()
        self.controller.last_message = ""
        self._destroy()

    def _on_finish(self) -> None:
        self._harvest_page()
        if self.controller.current_step is not SetupStep.REVIEW:
            self._set_message("Review every setup step before choosing Finish.")
            return
        allowed, message = self.controller.finish_allowed()
        if not allowed:
            self._set_message(message)
            return
        callbacks = build_setup_commit_callbacks(
            self.editor,
            self.controller.draft,
            config_only=self.controller.config_only,
        )
        try:
            result = self.controller.finish(callbacks)
        except _WIZARD_ERRORS + (tk.TclError,) as exc:
            self._set_message(f"Guided setup could not finish safely: {exc}")
            return
        if not result.ok:
            self._set_message(result.message)
            return
        self._cleanup_session()
        mark_saved = getattr(self.editor, "_mark_saved_snapshot", None)
        if callable(mark_saved):
            try:
                mark_saved()
            except _WIZARD_ERRORS + (tk.TclError,):
                logger.debug("guided setup could not refresh the saved-state marker", exc_info=True)
        self._destroy()
        self._safe_status("Guided setup complete")

    def _safe_status(self, message: str) -> None:
        from .wizard_parts.wizard_shell import report_status

        report_status(self, message)

    # -- rendering -----------------------------------------------------
    def _render(self) -> None:
        for child in list(self._body.winfo_children()):
            try:
                child.destroy()
            except _TK_ERRORS:
                pass
        self._overlay_entries = {}
        self._option_vars = {}
        self._option_labels = {}
        step = self.controller.current_step
        if step is SetupStep.PREFLIGHT:
            pages.render_preflight_page(self, ttk_module=ttk)
        elif step is SetupStep.LAYOUT:
            pages.render_layout_page(self, ttk_module=ttk, layout_labels=_layout_labels())
        elif step is SetupStep.OPTIONAL_KEYS:
            states = optional_slot_states(self.controller.draft)
            pages.render_optional_keys_page(self, ttk_module=ttk, tk_module=tk, tk_errors=_TK_ERRORS, states=states)
        elif step is SetupStep.CALIBRATION:
            pages.render_calibration_page(self, ttk_module=ttk, tk_errors=_TK_ERRORS)
        elif step is SetupStep.OVERLAY:
            pages.render_overlay_page(self, ttk_module=ttk, fields=_OVERLAY_FIELDS, defaults=_OVERLAY_DEFAULTS)
        else:
            pages.render_review_page(self, ttk_module=ttk)
        self._refresh_nav()

    def _refresh_nav(self) -> None:
        from .wizard_parts.wizard_shell import refresh_nav_state

        refresh_nav_state(self, tk_errors=_TK_ERRORS)

    def _harvest_page(self) -> None:
        from .wizard_parts.wizard_pages import harvest_current_page

        harvest_current_page(self)

    def _retry_preflight(self) -> None:
        from .wizard_parts.wizard_pages import retry_preflight

        retry_preflight(self, resolve_fn=resolve_setup_preflight)

    def _harvest_overlay(self) -> None:
        from .wizard_parts.wizard_pages import harvest_overlay_values

        harvest_overlay_values(self, tk_errors=_TK_ERRORS)

    def _harvest_optional_keys(self) -> None:
        from .wizard_parts.wizard_pages import harvest_optional_values

        harvest_optional_values(self, tk_errors=_TK_ERRORS, slot_states_fn=optional_slot_states)

    # -- guided calibrator child ---------------------------------------
    def _resolve_launcher(self) -> Callable[[object], object]:
        from .wizard_parts.wizard_child import resolve_child_launcher

        return resolve_child_launcher(self._launcher)

    def _on_launch_calibrator(self) -> None:
        from .wizard_parts.wizard_child import start_child_process

        start_child_process(
            self,
            create_session_fn=create_guided_session_file,
            cleanup_fn=cleanup_guided_session,
            launcher_fn=self._resolve_launcher(),
        )

    def _poll_child(self) -> None:
        from .wizard_parts.wizard_child import poll_child_process

        poll_child_process(self)

    def _finish_child(self) -> None:
        from .wizard_parts.wizard_child import finish_child_process

        finish_child_process(self, adopt_fn=adopt_guided_result)

    def _cleanup_session(self) -> None:
        from .wizard_parts.wizard_child import cleanup_child_session

        cleanup_child_session(self, cleanup_fn=cleanup_guided_session)

    def _cleanup_session_reference(self) -> None:
        from .wizard_parts.wizard_child import cleanup_session_reference

        cleanup_session_reference(self)
