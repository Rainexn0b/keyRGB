"""Clipboard/file export actions for the Support Tools window.

Owns the six copy/save wrappers' payload selection (diagnostics JSON,
discovery JSON, issue markdown) and delegates the actual clipboard/dialog
work to the window's ``_copy_text``/``_save_text_via_dialog`` methods so
``support.py`` stays small. Adds no behavior; all entry points remain on
``SupportToolsGUI`` via thin wrappers.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class _ExportWindow(Protocol):
    _diagnostics_json: str
    _discovery_json: str
    _issue_report: dict[str, object] | None

    def _copy_text(self, text: str, *, empty_message: str, ok_message: str) -> None: ...

    def _save_text_via_dialog(self, text: str, *, title: str, initialfile: str, empty_message: str) -> None: ...


def _issue_markdown(window: _ExportWindow) -> str:
    return str((window._issue_report or {}).get("markdown") or "")


def copy_debug_output(window: _ExportWindow) -> None:
    window._copy_text(
        window._diagnostics_json,
        empty_message="Run diagnostics first",
        ok_message="Diagnostics copied to clipboard",
    )


def save_debug_output(window: _ExportWindow) -> None:
    window._save_text_via_dialog(
        window._diagnostics_json,
        title="Save diagnostics output",
        initialfile="keyrgb-diagnostics.json",
        empty_message="Run diagnostics first",
    )


def copy_discovery_output(window: _ExportWindow) -> None:
    window._copy_text(
        window._discovery_json,
        empty_message="Run discovery first",
        ok_message="Discovery output copied to clipboard",
    )


def save_discovery_output(window: _ExportWindow) -> None:
    window._save_text_via_dialog(
        window._discovery_json,
        title="Save discovery output",
        initialfile="keyrgb-device-discovery.json",
        empty_message="Run discovery first",
    )


def copy_issue_report(window: _ExportWindow) -> None:
    window._copy_text(
        _issue_markdown(window),
        empty_message="Run diagnostics or discovery first",
        ok_message="Issue draft copied to clipboard",
    )


def save_issue_report(window: _ExportWindow) -> None:
    window._save_text_via_dialog(
        _issue_markdown(window),
        title="Save issue draft",
        initialfile="keyrgb-support-issue.md",
        empty_message="Run diagnostics or discovery first",
    )
