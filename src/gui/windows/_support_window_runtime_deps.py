"""Runtime import seam for the support-window facade."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk

from ._support import _support_window_actions as support_actions
from ._support import _support_window_jobs as support_jobs
from ._support import _support_window_runtime_services as support_runtime_services
from ._support import _support_window_session_bridge as support_session_bridge
from ._support import _support_window_state as support_window_state
from ._support import _support_window_ui as support_window_ui


__all__ = (
    "Config",
    "ISSUE_URL",
    "_BROWSER_OPEN_ERRORS",
    "_GEOMETRY_APPLY_ERRORS",
    "_TK_RUNTIME_ERRORS",
    "apply_clam_theme",
    "apply_keyrgb_window_icon",
    "build_additional_evidence_plan",
    "build_backend_speed_probe_plan",
    "build_issue_report_with_evidence",
    "build_support_bundle_payload",
    "center_window_on_screen",
    "collect_additional_evidence",
    "collect_device_discovery",
    "collect_diagnostics_text",
    "compute_centered_window_geometry",
    "filedialog",
    "format_device_discovery_text",
    "messagebox",
    "run_in_thread",
    "scrolledtext",
    "support_actions",
    "support_jobs",
    "support_session_bridge",
    "support_window_state",
    "support_window_ui",
    "tk",
    "ttk",
    "webbrowser",
)

_runtime_services = support_runtime_services.SupportWindowRuntimeServices

Config = _runtime_services.Config
ISSUE_URL = _runtime_services.ISSUE_URL
apply_clam_theme = _runtime_services.apply_clam_theme
apply_keyrgb_window_icon = _runtime_services.apply_keyrgb_window_icon
build_additional_evidence_plan = _runtime_services.build_additional_evidence_plan
build_backend_speed_probe_plan = _runtime_services.build_backend_speed_probe_plan
build_issue_report_with_evidence = _runtime_services.build_issue_report_with_evidence
build_support_bundle_payload = _runtime_services.build_support_bundle_payload
center_window_on_screen = _runtime_services.center_window_on_screen
collect_additional_evidence = _runtime_services.collect_additional_evidence
collect_device_discovery = _runtime_services.collect_device_discovery
collect_diagnostics_text = _runtime_services.collect_diagnostics_text
compute_centered_window_geometry = _runtime_services.compute_centered_window_geometry
format_device_discovery_text = _runtime_services.format_device_discovery_text
run_in_thread = _runtime_services.run_in_thread

_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_BROWSER_OPEN_ERRORS = (webbrowser.Error, OSError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
