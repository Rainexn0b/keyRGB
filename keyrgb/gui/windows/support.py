from __future__ import annotations

import logging
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING

from keyrgb.gui.utils.window_bindings import install_window_bindings
from keyrgb.gui.utils.window_state import WindowGeometryTracker

from . import _support_clipboard_actions as _clipboard_actions, _support_module_bundle as _module_bundle
from ._support._support_window_text_io import copy_text, save_text_via_dialog, set_status, set_text

support_actions = _module_bundle._support_window_actions
_support_window_geometry = _module_bundle._support_window_geometry
support_jobs = _module_bundle._support_window_jobs
_support_window_runtime_services = _module_bundle._support_window_runtime_services
support_session_bridge = _module_bundle._support_window_session_bridge
support_window_state = _module_bundle._support_window_state
support_window_ui = _module_bundle._support_window_ui

if TYPE_CHECKING:
    from keyrgb.gui.windows._support._support_window_state import (
        SupportSessionState as _SupportSessionState,
    )
    from keyrgb.gui.windows._support._support_window_ui_shared import (
        WrapTarget,
        _TextWidgetProtocol,
        _WidgetProtocol,
    )

_runtime_services = _support_window_runtime_services.SupportWindowRuntimeServices

Config = _runtime_services.Config
collect_device_discovery = _runtime_services.collect_device_discovery
format_device_discovery_text = _runtime_services.format_device_discovery_text
ISSUE_URL = _runtime_services.ISSUE_URL
build_additional_evidence_plan = _runtime_services.build_additional_evidence_plan
build_backend_speed_probe_plan = _runtime_services.build_backend_speed_probe_plan
build_issue_report_with_evidence = _runtime_services.build_issue_report_with_evidence
build_support_bundle_payload = _runtime_services.build_support_bundle_payload
collect_additional_evidence = _runtime_services.collect_additional_evidence
collect_diagnostics_text = _runtime_services.collect_diagnostics_text
apply_clam_theme = _runtime_services.apply_clam_theme
run_in_thread = _runtime_services.run_in_thread
center_window_on_screen = _runtime_services.center_window_on_screen
apply_keyrgb_window_icon = _runtime_services.apply_keyrgb_window_icon
compute_centered_window_geometry = _runtime_services.compute_centered_window_geometry


logger = logging.getLogger(__name__)
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_BROWSER_OPEN_ERRORS = (webbrowser.Error, OSError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


class SupportToolsGUI(support_session_bridge.SupportWindowSessionBridgeMixin):
    _geometry_restored = False
    _main_frame: _WidgetProtocol
    _wrap_targets: list[WrapTarget]
    status_label: _WidgetProtocol
    checks_frame: _WidgetProtocol
    debug_frame: _WidgetProtocol
    discovery_frame: _WidgetProtocol
    issue_frame: _WidgetProtocol
    bundle_frame: _WidgetProtocol
    issue_meta_label: _WidgetProtocol
    txt_debug: _TextWidgetProtocol
    txt_discovery: _TextWidgetProtocol
    txt_issue: _TextWidgetProtocol
    btn_run_debug: _WidgetProtocol
    btn_run_speed_probe: _WidgetProtocol
    btn_run_discovery: _WidgetProtocol
    btn_copy_debug: _WidgetProtocol
    btn_save_debug: _WidgetProtocol
    btn_copy_discovery: _WidgetProtocol
    btn_save_discovery: _WidgetProtocol
    btn_copy_issue: _WidgetProtocol
    btn_save_issue: _WidgetProtocol
    btn_collect_evidence: _WidgetProtocol
    btn_open_issue: _WidgetProtocol
    btn_save_bundle: _WidgetProtocol

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Support Tools")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(960, 720)
        self.root.resizable(True, True)

        bg_color, fg_color = apply_clam_theme(self.root)
        self._bg_color = bg_color
        self._fg_color = fg_color
        self._support_session = support_window_state.SupportSessionState()

        support_window_ui.build_window(
            self,
            ttk=ttk,
            scrolledtext=scrolledtext,
            center_window_on_screen=center_window_on_screen,
        )
        # UX-06: restore persisted geometry at the initial geometry pass. The
        # helper above always performs its immediate position-only centering;
        # restore() re-applies the saved size/position over it. When
        # restoration wins, the delayed centered pass is suppressed; otherwise
        # the exact previous fallback behavior runs. Tracking starts just
        # after the last initial programmatic pass. Dialogs are not persisted.
        self._geometry_tracker = WindowGeometryTracker(self.root, "support", 960, 720, 0.95)
        self._geometry_restored = bool(self._geometry_tracker.restore())
        if not self._geometry_restored:
            self.root.after(50, self._apply_geometry)
        self.root.after(60, self._geometry_tracker.start_tracking)
        protocol = getattr(self.root, "protocol", None)
        if callable(protocol):
            protocol("WM_DELETE_WINDOW", self._on_close)
        # UX-08: Ctrl+W/Escape share the exact orderly close above (additive,
        # focus-preserving; no save shortcut in Support).
        install_window_bindings(self.root, on_close=self._on_close)

        self._sync_button_state()

    @staticmethod
    def _support_session_cls() -> type[_SupportSessionState]:
        return support_window_state.SupportSessionState

    def _apply_geometry(self) -> None:
        if bool(vars(self).get("_geometry_restored", False)):
            return
        _support_window_geometry.apply_window_geometry(
            root=self.root,
            main_frame=self._main_frame,
            compute_centered_window_geometry=compute_centered_window_geometry,
            geometry_apply_errors=_GEOMETRY_APPLY_ERRORS,
        )

    def _apply_initial_focus(self) -> None:
        support_window_ui.apply_initial_focus(
            self,
            focus_env=str(os.environ.get("KEYRGB_SUPPORT_FOCUS") or "debug").strip().lower(),
        )

    def _sync_button_state(self) -> None:
        support_actions.sync_button_state(
            self,
            current_capture_plan_fn=self._current_capture_plan,
            current_backend_speed_probe_plan_fn=self._current_backend_speed_probe_plan,
            can_run_backend_speed_probe_fn=self._can_run_backend_speed_probe,
        )

    def _current_capture_plan(self) -> dict[str, object]:
        return support_actions.current_capture_plan(
            self,
            build_additional_evidence_plan=build_additional_evidence_plan,
            parsed_json_fn=self._parsed_json,
        )

    def _current_backend_speed_probe_plan(self) -> dict[str, object] | None:
        return support_actions.current_backend_speed_probe_plan(
            self,
            build_backend_speed_probe_plan=build_backend_speed_probe_plan,
            parsed_json_fn=self._parsed_json,
        )

    def _parsed_json(self, text: str) -> dict[str, object] | None:
        return support_actions.parsed_json(text)

    def _refresh_issue_report(self) -> None:
        support_actions.refresh_issue_report(
            self,
            parsed_json_fn=self._parsed_json,
            build_issue_report_with_evidence=build_issue_report_with_evidence,
            issue_url=ISSUE_URL,
        )

    def _maybe_prompt_for_missing_evidence(self) -> None:
        support_actions.maybe_prompt_for_missing_evidence(
            self,
            current_capture_plan_fn=self._current_capture_plan,
            messagebox=messagebox,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
        )

    def _maybe_prompt_for_backend_speed_probe(self) -> None:
        support_actions.maybe_prompt_for_backend_speed_probe(
            self,
            current_backend_speed_probe_plan_fn=self._current_backend_speed_probe_plan,
            can_run_backend_speed_probe_fn=self._can_run_backend_speed_probe,
            messagebox=messagebox,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
        )

    @staticmethod
    def _can_run_backend_speed_probe() -> bool:
        return support_jobs._tray_process_alive(str(os.environ.get("KEYRGB_TRAY_PID") or ""))

    def _merge_supplemental_evidence(self, payload: dict[str, object] | None) -> None:
        support_actions.merge_supplemental_evidence(self, payload)

    def _set_status(self, text: str, *, ok: bool = True) -> None:
        set_status(self, text, ok=ok)

    def _on_close(self) -> None:
        try:
            self._save_geometry_now()
        finally:
            self.root.destroy()

    def _save_geometry_now(self) -> None:
        tracker = vars(self).get("_geometry_tracker")
        save_now = getattr(tracker, "save_now", None)
        if callable(save_now):
            save_now()

    @staticmethod
    def _set_text(widget: object, text: str) -> None:
        set_text(widget, text)

    def _copy_text(self, text: str, *, empty_message: str, ok_message: str) -> None:
        copy_text(
            self,
            text,
            empty_message=empty_message,
            ok_message=ok_message,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
        )

    def _save_text_via_dialog(self, text: str, *, title: str, initialfile: str, empty_message: str) -> None:
        save_text_via_dialog(
            self,
            text,
            title=title,
            initialfile=initialfile,
            empty_message=empty_message,
            asksaveasfilename=filedialog.asksaveasfilename,
        )

    def run_debug(self) -> None:
        support_jobs.run_debug(
            self,
            collect_diagnostics_text=collect_diagnostics_text,
            run_in_thread=run_in_thread,
            logger=logger,
        )

    def run_discovery(self) -> None:
        support_jobs.run_discovery(
            self,
            collect_device_discovery=collect_device_discovery,
            format_device_discovery_text=format_device_discovery_text,
            run_in_thread=run_in_thread,
            logger=logger,
        )

    def collect_missing_evidence(self, *, prompt: bool = True) -> None:
        support_jobs.collect_missing_evidence(
            self,
            prompt=prompt,
            current_capture_plan_fn=self._current_capture_plan,
            messagebox=messagebox,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
            collect_additional_evidence=collect_additional_evidence,
            run_in_thread=run_in_thread,
        )

    def run_backend_speed_probe(self, *, prompt: bool = True) -> None:
        support_jobs.run_backend_speed_probe(
            self,
            prompt=prompt,
            current_backend_speed_probe_plan_fn=self._current_backend_speed_probe_plan,
            messagebox=messagebox,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
            run_in_thread=run_in_thread,
            config_cls=Config,
            tray_pid=str(os.environ.get("KEYRGB_TRAY_PID") or ""),
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
        )

    def copy_debug_output(self) -> None:
        _clipboard_actions.copy_debug_output(self)

    def save_debug_output(self) -> None:
        _clipboard_actions.save_debug_output(self)

    def copy_discovery_output(self) -> None:
        _clipboard_actions.copy_discovery_output(self)

    def save_discovery_output(self) -> None:
        _clipboard_actions.save_discovery_output(self)

    def copy_issue_report(self) -> None:
        _clipboard_actions.copy_issue_report(self)

    def save_issue_report(self) -> None:
        _clipboard_actions.save_issue_report(self)

    def save_support_bundle(self) -> None:
        support_jobs.save_support_bundle(
            self,
            asksaveasfilename=filedialog.asksaveasfilename,
            build_support_bundle_payload=build_support_bundle_payload,
            logger=logger,
            collect_diagnostics_text=collect_diagnostics_text,
            collect_device_discovery=collect_device_discovery,
        )

    def open_issue_form(self) -> None:
        support_jobs.open_issue_form(
            self,
            issue_url=ISSUE_URL,
            open_browser=webbrowser.open,
            browser_open_errors=_BROWSER_OPEN_ERRORS,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
        )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    from keyrgb.gui import single_instance

    single_instance.acquire_gui_instance_or_exit("support")
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    SupportToolsGUI().run()


if __name__ == "__main__":
    main()
