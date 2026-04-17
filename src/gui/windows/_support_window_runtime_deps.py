"""Runtime dependency aliases for the support-window facade."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext, ttk

from src.core.config import Config
from src.core.diagnostics import device_discovery as diagnostics_device_discovery
from src.core.diagnostics import support as diagnostics_support
from src.gui import theme as gui_theme
from src.gui.settings import diagnostics_runner
from src.gui.utils import tk_async, window_centering, window_icon
from src.gui.utils.window_geometry import compute_centered_window_geometry

from ._support import _support_window_actions as support_actions
from ._support import _support_window_jobs as support_jobs
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

_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_BROWSER_OPEN_ERRORS = (webbrowser.Error, OSError)
_GEOMETRY_APPLY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
