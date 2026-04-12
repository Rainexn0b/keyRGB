#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import webbrowser

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext, ttk

from src.core.config import Config
from src.core.diagnostics import device_discovery as diagnostics_device_discovery
from src.core.diagnostics import support as diagnostics_support
from src.gui.settings import diagnostics_runner
from src.gui import theme as gui_theme
from src.gui.utils import tk_async, window_centering, window_icon
from src.gui.utils.window_geometry import compute_centered_window_geometry

from ._support import _support_window_actions as support_actions
from ._support import _support_window_jobs as support_jobs
from ._support import _support_window_ui as support_window_ui


collect_device_discovery = diagnostics_device_discovery.collect_device_discovery
format_device_discovery_text = diagnostics_device_discovery.format_device_discovery_text
ISSUE_URL = diagnostics_support.ISSUE_URL
build_additional_evidence_plan = diagnostics_support.build_additional_evidence_plan
build_backend_speed_probe_plan = diagnostics_support.build_backend_speed_probe_plan
build_issue_report_with_evidence = diagnostics_support.build_issue_report_with_evidence
build_support_bundle_payload = diagnostics_support.build_support_bundle_payload
collect_additional_evidence = diagnostics_support.collect_additional_evidence
collect_diagnostics_text = diagnostics_runner.collect_diagnostics_text
apply_clam_theme = gui_theme.apply_clam_theme
run_in_thread = tk_async.run_in_thread
center_window_on_screen = window_centering.center_window_on_screen
apply_keyrgb_window_icon = window_icon.apply_keyrgb_window_icon


logger = logging.getLogger(__name__)
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_BROWSER_OPEN_ERRORS = (webbrowser.Error, OSError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


class SupportToolsGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Support Tools")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(960, 720)
        self.root.resizable(True, True)

        bg_color, fg_color = apply_clam_theme(self.root, include_checkbuttons=True, map_checkbutton_state=True)
        self._bg_color = bg_color
        self._fg_color = fg_color
        self._diagnostics_json = ""
        self._discovery_json = ""
        self._supplemental_evidence: dict[str, object] | None = None
        self._issue_report: dict[str, object] | None = None
        self._capture_prompt_key = ""
        self._backend_probe_prompt_key = ""

        support_window_ui.build_window(
            self, ttk=ttk, scrolledtext=scrolledtext, center_window_on_screen=center_window_on_screen
        )
        self.root.after(50, self._apply_geometry)

        self._sync_button_state()

    def _apply_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            geometry = compute_centered_window_geometry(
                self.root,
                content_height_px=int(self._main_frame.winfo_reqheight()),
                content_width_px=int(self._main_frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=48,
                default_w=1240,
                default_h=920,
                screen_ratio_cap=0.95,
            )
            self.root.geometry(geometry)
        except _GEOMETRY_APPLY_ERRORS:
            return

    def _build_debug_section(self, parent: ttk.LabelFrame) -> None:
        return

    def _build_discovery_section(self, parent: ttk.LabelFrame) -> None:
        return

    def _build_issue_section(self, parent: ttk.LabelFrame) -> None:
        return

    def _apply_initial_focus(self) -> None:
        support_window_ui.apply_initial_focus(
            self,
            focus_env=str(os.environ.get("KEYRGB_SUPPORT_FOCUS") or "debug").strip().lower(),
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
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
        support_actions.set_status(self, text, ok=ok)

    @staticmethod
    def _set_text(widget: scrolledtext.ScrolledText, text: str) -> None:
        support_actions.set_text(widget, text)

    def _copy_text(self, text: str, *, empty_message: str, ok_message: str) -> None:
        support_actions.copy_text(
            self,
            text,
            empty_message=empty_message,
            ok_message=ok_message,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
        )

    def _save_text_via_dialog(self, text: str, *, title: str, initialfile: str, empty_message: str) -> None:
        support_actions.save_text_via_dialog(
            self,
            text,
            title=title,
            initialfile=initialfile,
            empty_message=empty_message,
            asksaveasfilename=filedialog.asksaveasfilename,
        )

    def run_debug(self) -> None:
        support_jobs.run_debug(
            self, collect_diagnostics_text=collect_diagnostics_text, run_in_thread=run_in_thread, logger=logger
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
        self._copy_text(
            self._diagnostics_json,
            empty_message="Run diagnostics first",
            ok_message="Diagnostics copied to clipboard",
        )

    def save_debug_output(self) -> None:
        self._save_text_via_dialog(
            self._diagnostics_json,
            title="Save diagnostics output",
            initialfile="keyrgb-diagnostics.json",
            empty_message="Run diagnostics first",
        )

    def copy_discovery_output(self) -> None:
        self._copy_text(
            self._discovery_json,
            empty_message="Run discovery first",
            ok_message="Discovery output copied to clipboard",
        )

    def save_discovery_output(self) -> None:
        self._save_text_via_dialog(
            self._discovery_json,
            title="Save discovery output",
            initialfile="keyrgb-device-discovery.json",
            empty_message="Run discovery first",
        )

    def copy_issue_report(self) -> None:
        text = str((self._issue_report or {}).get("markdown") or "")
        self._copy_text(
            text,
            empty_message="Run diagnostics or discovery first",
            ok_message="Issue draft copied to clipboard",
        )

    def save_issue_report(self) -> None:
        text = str((self._issue_report or {}).get("markdown") or "")
        self._save_text_via_dialog(
            text,
            title="Save issue draft",
            initialfile="keyrgb-support-issue.md",
            empty_message="Run diagnostics or discovery first",
        )

    def save_support_bundle(self) -> None:
        support_jobs.save_support_bundle(
            self,
            asksaveasfilename=filedialog.asksaveasfilename,
            build_support_bundle_payload=build_support_bundle_payload,
            logger=logger,
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
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    SupportToolsGUI().run()


if __name__ == "__main__":
    main()
