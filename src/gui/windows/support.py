#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
import webbrowser

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext, ttk

from src.core.diagnostics.additional_evidence import build_additional_evidence_plan, collect_additional_evidence
from src.core.diagnostics.device_discovery import collect_device_discovery, format_device_discovery_text
from src.core.diagnostics.support_reports import (
    ISSUE_URL,
    build_issue_report_with_evidence,
    build_support_bundle_payload,
)
from src.gui.settings.diagnostics_runner import collect_diagnostics_text
from src.gui.theme import apply_clam_theme
from src.gui.utils.tk_async import run_in_thread
from src.gui.utils.window_centering import center_window_on_screen
from src.gui.utils.window_icon import apply_keyrgb_window_icon


logger = logging.getLogger(__name__)
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_BROWSER_OPEN_ERRORS = (webbrowser.Error, OSError)


class SupportToolsGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Support Tools")
        apply_keyrgb_window_icon(self.root)
        self.root.geometry("980x980")
        self.root.minsize(880, 820)
        self.root.resizable(True, True)

        bg_color, fg_color = apply_clam_theme(self.root, include_checkbuttons=True, map_checkbutton_state=True)
        self._bg_color = bg_color
        self._fg_color = fg_color
        self._diagnostics_json = ""
        self._discovery_json = ""
        self._supplemental_evidence: dict[str, object] | None = None
        self._issue_report: dict[str, object] | None = None
        self._capture_prompt_key = ""

        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Support Tools", font=("Sans", 14, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            main,
            text=(
                "Run read-only support scans directly from the tray workflow.\n"
                "The Debug section explains the current setup; Detect New Backends highlights RGB-related devices that keyRGB sees but may not yet support."
            ),
            font=("Sans", 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self.status_label = ttk.Label(main, text="", font=("Sans", 9))
        self.status_label.pack(anchor="w", pady=(0, 10))

        self.debug_frame = ttk.LabelFrame(main, text="Debug", padding=12)
        self.debug_frame.pack(fill="both", expand=True, pady=(0, 12))
        self._build_debug_section(self.debug_frame)

        self.discovery_frame = ttk.LabelFrame(main, text="Detect New Backends", padding=12)
        self.discovery_frame.pack(fill="both", expand=True)
        self._build_discovery_section(self.discovery_frame)

        self.issue_frame = ttk.LabelFrame(main, text="Prepare Support Issue", padding=12)
        self.issue_frame.pack(fill="both", expand=True, pady=(12, 0))
        self._build_issue_section(self.issue_frame)

        self._sync_button_state()

        center_window_on_screen(self.root)
        self.root.after(150, self._apply_initial_focus)

    def _build_debug_section(self, parent: ttk.LabelFrame) -> None:
        ttk.Label(
            parent,
            text="Collect a full read-only diagnostics report for the current setup, including backend probes, USB holders, and configuration state.",
            font=("Sans", 9),
            justify="left",
            wraplength=860,
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))

        self.btn_run_debug = ttk.Button(row, text="Run diagnostics", command=self.run_debug)
        self.btn_run_debug.pack(side="left")
        self.btn_copy_debug = ttk.Button(row, text="Copy output", command=self.copy_debug_output)
        self.btn_copy_debug.pack(side="left", padx=(8, 0))
        self.btn_save_debug = ttk.Button(row, text="Save diagnostics JSON…", command=self.save_debug_output)
        self.btn_save_debug.pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Open issue", command=self.open_issue_form).pack(side="left", padx=(8, 0))

        self.txt_debug = scrolledtext.ScrolledText(
            parent,
            height=12,
            wrap="word",
            background=self._bg_color,
            foreground=self._fg_color,
            insertbackground=self._fg_color,
        )
        self.txt_debug.pack(fill="both", expand=True)
        self.txt_debug.insert("1.0", "Click 'Run diagnostics' to collect the current support report.\n")
        self.txt_debug.configure(state="disabled")

    def _build_discovery_section(self, parent: ttk.LabelFrame) -> None:
        ttk.Label(
            parent,
            text="Scan for supported, dormant, experimental-disabled, and unrecognized ITE-class controller candidates using safe read-only probes.",
            font=("Sans", 9),
            justify="left",
            wraplength=860,
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))

        self.btn_run_discovery = ttk.Button(row, text="Scan devices", command=self.run_discovery)
        self.btn_run_discovery.pack(side="left")
        self.btn_copy_discovery = ttk.Button(row, text="Copy output", command=self.copy_discovery_output)
        self.btn_copy_discovery.pack(side="left", padx=(8, 0))
        self.btn_save_discovery = ttk.Button(row, text="Save discovery JSON…", command=self.save_discovery_output)
        self.btn_save_discovery.pack(side="left", padx=(8, 0))
        self.btn_save_bundle = ttk.Button(row, text="Save full support bundle…", command=self.save_support_bundle)
        self.btn_save_bundle.pack(side="left", padx=(8, 0))

        self.txt_discovery = scrolledtext.ScrolledText(
            parent,
            height=10,
            wrap="word",
            background=self._bg_color,
            foreground=self._fg_color,
            insertbackground=self._fg_color,
        )
        self.txt_discovery.pack(fill="both", expand=True)
        self.txt_discovery.insert("1.0", "Click 'Scan devices' to identify supported and unsupported backend candidates.\n")
        self.txt_discovery.configure(state="disabled")

    def _build_issue_section(self, parent: ttk.LabelFrame) -> None:
        ttk.Label(
            parent,
            text=(
                "Review the recommended GitHub form before filing. The draft updates automatically from the current diagnostics and discovery results."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=860,
        ).pack(anchor="w", pady=(0, 8))

        self.issue_meta_label = ttk.Label(
            parent,
            text="Suggested template: run diagnostics or discovery first",
            font=("Sans", 9),
            justify="left",
        )
        self.issue_meta_label.pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))

        self.btn_copy_issue = ttk.Button(row, text="Copy issue draft", command=self.copy_issue_report)
        self.btn_copy_issue.pack(side="left")
        self.btn_save_issue = ttk.Button(row, text="Save issue draft…", command=self.save_issue_report)
        self.btn_save_issue.pack(side="left", padx=(8, 0))
        self.btn_collect_evidence = ttk.Button(
            row,
            text="Collect missing evidence…",
            command=self.collect_missing_evidence,
        )
        self.btn_collect_evidence.pack(side="left", padx=(8, 0))
        self.btn_open_issue = ttk.Button(row, text="Open suggested issue", command=self.open_issue_form)
        self.btn_open_issue.pack(side="left", padx=(8, 0))

        self.txt_issue = scrolledtext.ScrolledText(
            parent,
            height=11,
            wrap="word",
            background=self._bg_color,
            foreground=self._fg_color,
            insertbackground=self._fg_color,
        )
        self.txt_issue.pack(fill="both", expand=True)
        self.txt_issue.insert(
            "1.0",
            "Run diagnostics or discovery to generate a suggested issue draft and the recommended GitHub form.\n",
        )
        self.txt_issue.configure(state="disabled")

    def _apply_initial_focus(self) -> None:
        focus = str(os.environ.get("KEYRGB_SUPPORT_FOCUS") or "debug").strip().lower()
        try:
            if focus == "discovery":
                self.discovery_frame.focus_set()
                self.txt_discovery.focus_set()
            else:
                self.debug_frame.focus_set()
                self.txt_debug.focus_set()
        except _TK_RUNTIME_ERRORS:
            return

    def _sync_button_state(self) -> None:
        self.btn_copy_debug.configure(state="normal" if self._diagnostics_json else "disabled")
        self.btn_copy_discovery.configure(state="normal" if self._discovery_json else "disabled")
        self.btn_save_debug.configure(state="normal" if self._diagnostics_json else "disabled")
        self.btn_save_discovery.configure(state="normal" if self._discovery_json else "disabled")
        plan = self._current_capture_plan()
        has_capture_plan = bool(plan.get("automated"))
        issue_state = "normal" if self._issue_report and self._issue_report.get("markdown") else "disabled"
        self.btn_copy_issue.configure(state=issue_state)
        self.btn_save_issue.configure(state=issue_state)
        self.btn_open_issue.configure(state=issue_state)
        self.btn_collect_evidence.configure(state="normal" if has_capture_plan else "disabled")
        self.btn_save_bundle.configure(
            state="normal" if (self._diagnostics_json or self._discovery_json) else "disabled"
        )

    def _current_capture_plan(self) -> dict[str, object]:
        return build_additional_evidence_plan(self._parsed_json(self._discovery_json))

    def _parsed_json(self, text: str) -> dict[str, object] | None:
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _refresh_issue_report(self) -> None:
        diagnostics = self._parsed_json(self._diagnostics_json)
        discovery = self._parsed_json(self._discovery_json)
        if diagnostics is None and discovery is None:
            self._issue_report = None
            self.issue_meta_label.configure(text="Suggested template: run diagnostics or discovery first")
            self._set_text(
                self.txt_issue,
                "Run diagnostics or discovery to generate a suggested issue draft and the recommended GitHub form.\n",
            )
            return
        self._issue_report = build_issue_report_with_evidence(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=self._supplemental_evidence if isinstance(self._supplemental_evidence, dict) else None,
        )
        template_label = str(self._issue_report.get("template_label") or "Issue report")
        issue_url = str(self._issue_report.get("issue_url") or ISSUE_URL)
        self.issue_meta_label.configure(text=f"Suggested template: {template_label}\nIssue URL: {issue_url}")
        self._set_text(self.txt_issue, str(self._issue_report.get("markdown") or ""))

    def _maybe_prompt_for_missing_evidence(self) -> None:
        plan = self._current_capture_plan()
        automated = plan.get("automated") if isinstance(plan, dict) else None
        if not isinstance(automated, list) or not automated:
            return

        usb_id = str(plan.get("usb_id") or "")
        prompt_key = usb_id + ":" + ",".join(str(item.get("key") or "") for item in automated if isinstance(item, dict))
        if not prompt_key or prompt_key == self._capture_prompt_key:
            return
        self._capture_prompt_key = prompt_key

        needs_privileged = any(bool(item.get("requires_root")) for item in automated if isinstance(item, dict))
        message = "KeyRGB can collect additional evidence for this unsupported device now."
        if needs_privileged:
            message += " This may prompt for an administrator password to run read-only capture tools."
        message += "\n\nCollect missing evidence now?"

        try:
            ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=self.root))
        except _TK_RUNTIME_ERRORS:
            ok = False
        if ok:
            self.collect_missing_evidence(prompt=False)

    def _set_status(self, text: str, *, ok: bool = True) -> None:
        color = "#00aa00" if ok else "#bb0000"
        self.status_label.configure(text=text, foreground=color)
        self.root.after(2500, lambda: self.status_label.configure(text=""))

    @staticmethod
    def _set_text(widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _copy_text(self, text: str, *, empty_message: str, ok_message: str) -> None:
        if not text:
            self._set_status(empty_message, ok=False)
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except _TK_RUNTIME_ERRORS:
            self._set_status("Clipboard copy failed", ok=False)
            return
        self._set_status(ok_message, ok=True)

    def _save_text_via_dialog(self, text: str, *, title: str, initialfile: str, empty_message: str) -> None:
        if not text:
            self._set_status(empty_message, ok=False)
            return

        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".json",
            initialfile=initialfile,
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            self._set_status("Failed to save file", ok=False)
            return

        self._set_status("Saved output", ok=True)

    def run_debug(self) -> None:
        self.btn_run_debug.configure(state="disabled")
        self.btn_copy_debug.configure(state="disabled")
        self._set_status("Collecting diagnostics…", ok=True)

        def work() -> str:
            try:
                return collect_diagnostics_text(include_usb=True)
            except Exception as exc:
                logger.exception("Failed to collect diagnostics")
                return f"Failed to collect diagnostics: {exc}"

        def on_done(text: str) -> None:
            self._diagnostics_json = text if text.strip().startswith("{") else ""
            self._set_text(self.txt_debug, text)
            self.btn_run_debug.configure(state="normal")
            self._refresh_issue_report()
            self._sync_button_state()
            self._set_status("Diagnostics ready", ok=bool(self._diagnostics_json))

        run_in_thread(self.root, work, on_done)

    def run_discovery(self) -> None:
        self.btn_run_discovery.configure(state="disabled")
        self.btn_copy_discovery.configure(state="disabled")
        self._set_status("Scanning backend candidates…", ok=True)

        def work() -> tuple[str, str]:
            try:
                payload = collect_device_discovery(include_usb=True)
                return json.dumps(payload, indent=2, sort_keys=True), format_device_discovery_text(payload)
            except Exception as exc:
                logger.exception("Failed to collect discovery snapshot")
                text = f"Failed to scan devices: {exc}"
                return "", text

        def on_done(result: tuple[str, str]) -> None:
            payload_text, display_text = result
            self._discovery_json = payload_text
            self._supplemental_evidence = None
            self._set_text(self.txt_discovery, display_text)
            self.btn_run_discovery.configure(state="normal")
            self._refresh_issue_report()
            self._sync_button_state()
            self._set_status("Discovery scan ready", ok=bool(self._discovery_json))
            self._maybe_prompt_for_missing_evidence()

        run_in_thread(self.root, work, on_done)

    def collect_missing_evidence(self, *, prompt: bool = True) -> None:
        plan = self._current_capture_plan()
        automated = plan.get("automated") if isinstance(plan, dict) else None
        if not isinstance(automated, list) or not automated:
            self._set_status("No extra evidence needed", ok=False)
            return

        if prompt:
            needs_privileged = any(bool(item.get("requires_root")) for item in automated if isinstance(item, dict))
            message = "Collect additional USB/HID evidence for the current unsupported device?"
            if needs_privileged:
                message += " This may prompt for an administrator password."
            try:
                ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=self.root))
            except _TK_RUNTIME_ERRORS:
                ok = False
            if not ok:
                return

        self.btn_collect_evidence.configure(state="disabled")
        self._set_status("Collecting additional evidence…", ok=True)

        def work() -> dict[str, object]:
            return collect_additional_evidence(self._parsed_json(self._discovery_json), allow_privileged=True)

        def on_done(payload: dict[str, object]) -> None:
            self._supplemental_evidence = payload if isinstance(payload, dict) else None
            self._refresh_issue_report()
            self._sync_button_state()
            captures = payload.get("captures") if isinstance(payload, dict) else None
            success = 0
            if isinstance(captures, dict):
                success = sum(1 for value in captures.values() if isinstance(value, dict) and value.get("ok"))
            self._set_status("Additional evidence collected" if success else "Additional evidence incomplete", ok=bool(success))

        run_in_thread(self.root, work, on_done)

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
        if not self._diagnostics_json and not self._discovery_json:
            self._set_status("Run diagnostics or discovery first", ok=False)
            return

        path = filedialog.asksaveasfilename(
            title="Save support bundle",
            defaultextension=".json",
            initialfile="keyrgb-support-bundle.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            payload = build_support_bundle_payload(
                diagnostics=self._parsed_json(self._diagnostics_json),
                discovery=self._parsed_json(self._discovery_json),
                supplemental_evidence=self._supplemental_evidence if isinstance(self._supplemental_evidence, dict) else None,
            )
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
        except (OSError, TypeError, ValueError):
            self._set_status("Failed to save bundle", ok=False)
            return
        except Exception:
            logger.exception("Failed to save support bundle")
            self._set_status("Failed to save bundle", ok=False)
            return

        self._set_status("Saved support bundle", ok=True)

    def open_issue_form(self) -> None:
        issue_url = str((self._issue_report or {}).get("issue_url") or ISSUE_URL)
        try:
            ok = bool(webbrowser.open(issue_url, new=2))
        except _BROWSER_OPEN_ERRORS:
            ok = False

        if ok:
            self._set_status("Opened issue form", ok=True)
            return

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(issue_url)
            self._set_status("Couldn't open browser; issue URL copied", ok=False)
        except _TK_RUNTIME_ERRORS:
            self._set_status("Couldn't open browser", ok=False)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    SupportToolsGUI().run()


if __name__ == "__main__":
    main()