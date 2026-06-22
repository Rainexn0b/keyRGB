#!/usr/bin/env python3

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Protocol, TypeAlias, cast

_JsonDict: TypeAlias = dict[str, object]


class _WindowRoot(Protocol):
    def clipboard_clear(self) -> None: ...

    def clipboard_append(self, value: str) -> None: ...


class _SupportWindow(Protocol):
    root: _WindowRoot
    _diagnostics_json: str
    _discovery_json: str
    _supplemental_evidence: object
    _issue_report: Mapping[str, object] | None

    def _set_status(self, text: str, *, ok: bool = True) -> None: ...

    def _parsed_json(self, text: str) -> _JsonDict | None: ...


class _AskSaveAsFilename(Protocol):
    def __call__(
        self,
        *,
        title: str,
        defaultextension: str,
        initialfile: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> str: ...


class _BuildSupportBundlePayload(Protocol):
    def __call__(
        self,
        *,
        diagnostics: _JsonDict | None,
        discovery: _JsonDict | None,
        supplemental_evidence: _JsonDict | None = None,
    ) -> _JsonDict: ...


class _CollectDiagnosticsText(Protocol):
    def __call__(self, *, include_usb: bool) -> str: ...


class _CollectDeviceDiscovery(Protocol):
    def __call__(self, *, include_usb: bool) -> _JsonDict: ...


class _Logger(Protocol):
    def exception(self, message: str) -> None: ...


class _OpenBrowser(Protocol):
    def __call__(self, url: str, new: int = 0) -> bool: ...


def _json_dict_or_none(value: object) -> _JsonDict | None:
    return cast(_JsonDict, value) if isinstance(value, dict) else None


_SUPPORT_BUNDLE_BUILD_ERRORS = (AttributeError, LookupError, RuntimeError)
_SUPPORT_BUNDLE_AUTOFILL_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _autofill_missing_bundle_snapshots(
    window: _SupportWindow,
    *,
    collect_diagnostics_text: _CollectDiagnosticsText | None,
    collect_device_discovery: _CollectDeviceDiscovery | None,
    logger: _Logger,
) -> None:
    if not window._diagnostics_json and collect_diagnostics_text is not None:
        try:
            diagnostics_text = collect_diagnostics_text(include_usb=True)
        except _SUPPORT_BUNDLE_AUTOFILL_ERRORS:
            logger.exception("Failed to auto-collect diagnostics for support bundle")
        else:
            if str(diagnostics_text or "").strip().startswith("{"):
                window._diagnostics_json = str(diagnostics_text)

    if not window._discovery_json and collect_device_discovery is not None:
        try:
            discovery = collect_device_discovery(include_usb=True)
        except _SUPPORT_BUNDLE_AUTOFILL_ERRORS:
            logger.exception("Failed to auto-collect device discovery for support bundle")
        else:
            if isinstance(discovery, dict):
                window._discovery_json = json.dumps(discovery, indent=2, sort_keys=True)


def save_support_bundle(
    window: _SupportWindow,
    *,
    asksaveasfilename: _AskSaveAsFilename,
    build_support_bundle_payload: _BuildSupportBundlePayload,
    logger: _Logger,
    collect_diagnostics_text: _CollectDiagnosticsText | None = None,
    collect_device_discovery: _CollectDeviceDiscovery | None = None,
) -> None:
    _autofill_missing_bundle_snapshots(
        window,
        collect_diagnostics_text=collect_diagnostics_text,
        collect_device_discovery=collect_device_discovery,
        logger=logger,
    )

    if not window._diagnostics_json and not window._discovery_json:
        window._set_status("Run diagnostics or discovery first", ok=False)
        return

    path = asksaveasfilename(
        title="Save support bundle",
        defaultextension=".json",
        initialfile="keyrgb-support-bundle.json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        payload = build_support_bundle_payload(
            diagnostics=window._parsed_json(window._diagnostics_json),
            discovery=window._parsed_json(window._discovery_json),
            supplemental_evidence=_json_dict_or_none(window._supplemental_evidence),
        )
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (OSError, TypeError, ValueError):
        window._set_status("Failed to save bundle", ok=False)
        return
    except _SUPPORT_BUNDLE_BUILD_ERRORS:
        logger.exception("Failed to save support bundle")
        window._set_status("Failed to save bundle", ok=False)
        return

    window._set_status("Saved support bundle", ok=True)


def open_issue_form(
    window: _SupportWindow,
    *,
    issue_url: str,
    open_browser: _OpenBrowser,
    browser_open_errors: tuple[type[BaseException], ...],
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    resolved_issue_url = str((window._issue_report or {}).get("issue_url") or issue_url)
    try:
        ok = bool(open_browser(resolved_issue_url, new=2))
    except browser_open_errors:
        ok = False

    if ok:
        window._set_status("Opened issue form", ok=True)
        return

    try:
        window.root.clipboard_clear()
        window.root.clipboard_append(resolved_issue_url)
        window._set_status("Couldn't open browser; issue URL copied", ok=False)
    except tk_runtime_errors:
        window._set_status("Couldn't open browser", ok=False)
