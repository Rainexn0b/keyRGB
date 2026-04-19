"""Grouped non-Tk runtime services for the support-window dependency seam."""

from __future__ import annotations

from src.core import config as core_config
from src.core.diagnostics import device_discovery as diagnostics_device_discovery
from src.core.diagnostics import support as diagnostics_support
from src.gui import theme as gui_theme
from src.gui.settings import diagnostics_runner
from src.gui.utils import tk_async, window_centering, window_geometry, window_icon


class SupportWindowRuntimeServices:
    Config = core_config.Config
    ISSUE_URL = diagnostics_support.ISSUE_URL
    apply_clam_theme = gui_theme.apply_clam_theme
    apply_keyrgb_window_icon = window_icon.apply_keyrgb_window_icon
    build_additional_evidence_plan = diagnostics_support.build_additional_evidence_plan
    build_backend_speed_probe_plan = diagnostics_support.build_backend_speed_probe_plan
    build_issue_report_with_evidence = diagnostics_support.build_issue_report_with_evidence
    build_support_bundle_payload = diagnostics_support.build_support_bundle_payload
    center_window_on_screen = window_centering.center_window_on_screen
    collect_additional_evidence = diagnostics_support.collect_additional_evidence
    collect_device_discovery = diagnostics_device_discovery.collect_device_discovery
    collect_diagnostics_text = diagnostics_runner.collect_diagnostics_text
    compute_centered_window_geometry = window_geometry.compute_centered_window_geometry
    format_device_discovery_text = diagnostics_device_discovery.format_device_discovery_text
    run_in_thread = tk_async.run_in_thread