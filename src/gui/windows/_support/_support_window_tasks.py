#!/usr/bin/env python3

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol, TypeAlias


_JsonDict: TypeAlias = dict[str, object]

_SUPPORT_COLLECTION_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _TaskWindowBase(Protocol):
    root: object

    def _set_status(self, text: str, *, ok: bool = True) -> None: ...

    def _refresh_issue_report(self) -> None: ...

    def _sync_button_state(self) -> None: ...


class _DebugWindow(_TaskWindowBase, Protocol):
    btn_run_debug: _ConfigurableWidget
    btn_copy_debug: _ConfigurableWidget
    txt_debug: object
    _diagnostics_json: str

    def _set_text(self, widget: object, text: str) -> None: ...

    def _maybe_prompt_for_backend_speed_probe(self) -> None: ...


class _DiscoveryWindow(_TaskWindowBase, Protocol):
    btn_run_discovery: _ConfigurableWidget
    btn_copy_discovery: _ConfigurableWidget
    txt_discovery: object
    _discovery_json: str
    _supplemental_evidence: _JsonDict | None

    def _set_text(self, widget: object, text: str) -> None: ...

    def _maybe_prompt_for_missing_evidence(self) -> None: ...

    def _maybe_prompt_for_backend_speed_probe(self) -> None: ...


class _EvidenceWindow(_TaskWindowBase, Protocol):
    btn_collect_evidence: _ConfigurableWidget
    _discovery_json: str

    def _parsed_json(self, text: str) -> _JsonDict | None: ...

    def _merge_supplemental_evidence(self, payload: _JsonDict | None) -> None: ...


class _Logger(Protocol):
    def exception(self, message: str) -> None: ...


class _CollectDiagnosticsText(Protocol):
    def __call__(self, *, include_usb: bool) -> str: ...


class _RunDebugInThread(Protocol):
    def __call__(
        self,
        root: object,
        work: Callable[[], str],
        on_done: Callable[[str], None],
    ) -> None: ...


class _CollectDeviceDiscovery(Protocol):
    def __call__(self, *, include_usb: bool) -> _JsonDict: ...


class _FormatDeviceDiscoveryText(Protocol):
    def __call__(self, payload: _JsonDict) -> str: ...


class _RunDiscoveryInThread(Protocol):
    def __call__(
        self,
        root: object,
        work: Callable[[], tuple[str, str]],
        on_done: Callable[[tuple[str, str]], None],
    ) -> None: ...


class _CurrentCapturePlanFn(Protocol):
    def __call__(self) -> _JsonDict | None: ...


class _MessageBox(Protocol):
    def askyesno(self, title: str, message: str, *, parent: object) -> object: ...


class _CollectAdditionalEvidence(Protocol):
    def __call__(self, discovery: _JsonDict | None, *, allow_privileged: bool) -> object: ...


class _RunEvidenceInThread(Protocol):
    def __call__(
        self,
        root: object,
        work: Callable[[], object],
        on_done: Callable[[object], None],
    ) -> None: ...


def _json_dict(value: object) -> _JsonDict | None:
    return value if isinstance(value, dict) else None


def _automated_capture_steps(plan: _JsonDict | None) -> list[_JsonDict]:
    automated = plan.get("automated") if isinstance(plan, dict) else None
    if not isinstance(automated, list):
        return []
    return [item for item in automated if isinstance(item, dict)]


def _existing_backend_probes(supplemental_evidence: _JsonDict | None) -> _JsonDict | None:
    if not isinstance(supplemental_evidence, dict):
        return None
    backend_probes = _json_dict(supplemental_evidence.get("backend_probes"))
    return dict(backend_probes) if backend_probes else None


def run_debug(
    window: _DebugWindow,
    *,
    collect_diagnostics_text: _CollectDiagnosticsText,
    run_in_thread: _RunDebugInThread,
    logger: _Logger,
) -> None:
    window.btn_run_debug.configure(state="disabled")
    window.btn_copy_debug.configure(state="disabled")
    window._set_status("Collecting diagnostics…", ok=True)

    def work() -> str:
        try:
            return collect_diagnostics_text(include_usb=True)
        except _SUPPORT_COLLECTION_ERRORS as exc:
            logger.exception("Failed to collect diagnostics")
            return f"Failed to collect diagnostics: {exc}"

    def on_done(text: str) -> None:
        window._diagnostics_json = text if text.strip().startswith("{") else ""
        window._set_text(window.txt_debug, text)
        window.btn_run_debug.configure(state="normal")
        window._refresh_issue_report()
        window._sync_button_state()
        window._set_status("Diagnostics ready", ok=bool(window._diagnostics_json))
        window._maybe_prompt_for_backend_speed_probe()

    run_in_thread(window.root, work, on_done)


def run_discovery(
    window: _DiscoveryWindow,
    *,
    collect_device_discovery: _CollectDeviceDiscovery,
    format_device_discovery_text: _FormatDeviceDiscoveryText,
    run_in_thread: _RunDiscoveryInThread,
    logger: _Logger,
) -> None:
    window.btn_run_discovery.configure(state="disabled")
    window.btn_copy_discovery.configure(state="disabled")
    window._set_status("Scanning backend candidates…", ok=True)

    def work() -> tuple[str, str]:
        try:
            payload = collect_device_discovery(include_usb=True)
            return json.dumps(payload, indent=2, sort_keys=True), format_device_discovery_text(payload)
        except _SUPPORT_COLLECTION_ERRORS as exc:
            logger.exception("Failed to collect discovery snapshot")
            return "", f"Failed to scan devices: {exc}"

    def on_done(result: tuple[str, str]) -> None:
        payload_text, display_text = result
        window._discovery_json = payload_text
        backend_probes = _existing_backend_probes(window._supplemental_evidence)
        window._supplemental_evidence = {"backend_probes": backend_probes} if backend_probes else None
        window._set_text(window.txt_discovery, display_text)
        window.btn_run_discovery.configure(state="normal")
        window._refresh_issue_report()
        window._sync_button_state()
        window._set_status("Discovery scan ready", ok=bool(window._discovery_json))
        window._maybe_prompt_for_missing_evidence()
        window._maybe_prompt_for_backend_speed_probe()

    run_in_thread(window.root, work, on_done)


def collect_missing_evidence(
    window: _EvidenceWindow,
    *,
    prompt: bool,
    current_capture_plan_fn: _CurrentCapturePlanFn,
    messagebox: _MessageBox,
    tk_runtime_errors: tuple[type[BaseException], ...],
    collect_additional_evidence: _CollectAdditionalEvidence,
    run_in_thread: _RunEvidenceInThread,
) -> None:
    automated = _automated_capture_steps(current_capture_plan_fn())
    if not automated:
        window._set_status("No extra evidence needed", ok=False)
        return

    if prompt:
        needs_privileged = any(bool(item.get("requires_root")) for item in automated)
        message = "Collect additional USB/HID evidence for the current unsupported device?"
        if needs_privileged:
            message += " This may prompt for an administrator password."
        try:
            ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=window.root))
        except tk_runtime_errors:
            ok = False
        if not ok:
            return

    window.btn_collect_evidence.configure(state="disabled")
    window._set_status("Collecting additional evidence…", ok=True)

    def work() -> object:
        return collect_additional_evidence(window._parsed_json(window._discovery_json), allow_privileged=True)

    def on_done(payload: object) -> None:
        payload_dict = _json_dict(payload)
        window._merge_supplemental_evidence(payload_dict)
        window._refresh_issue_report()
        window._sync_button_state()
        captures = _json_dict(payload_dict.get("captures")) if payload_dict is not None else None
        success = 0
        if captures is not None:
            success = sum(1 for value in captures.values() if isinstance(value, dict) and value.get("ok"))
        window._set_status(
            "Additional evidence collected" if success else "Additional evidence incomplete", ok=bool(success)
        )

    run_in_thread(window.root, work, on_done)
