from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.core.backends.policy import (
    experimental_backends_enabled,
    experimental_evidence_for_backend,
    selection_allowed_for_backend,
    stability_for_backend,
)
from src.core.utils.safe_attrs import safe_int_attr

from ..support import build_backend_speed_probe_plans
from ._backends_sysfs import sysfs_led_candidates_snapshot, sysfs_mouse_candidates_snapshot


logger = logging.getLogger(__name__)

_BACKEND_METADATA_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_IDENTIFIER_NORMALIZATION_ERRORS = (AttributeError, TypeError, ValueError)
_SORT_VALUE_ERRORS = (OverflowError, RuntimeError, TypeError, ValueError)


def _log_snapshot_boundary(message: str, exc: Exception) -> None:
    logger.log(logging.DEBUG, message, exc_info=(type(exc), exc, exc.__traceback__))


def _coerce_sort_value(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(value)  # type: ignore[call-overload]
    except _SORT_VALUE_ERRORS:
        return 0


def _tier_for_backend_name(name: str) -> int | None:
    normalized = (name or "").strip().lower()
    if normalized == "sysfs-leds":
        return 1
    if normalized == "sysfs-mouse":
        return 1
    if normalized.startswith("ite"):
        return 2
    return None


def _provider_for_backend_name(name: str) -> str | None:
    normalized = (name or "").strip().lower()
    if normalized == "sysfs-leds":
        return "kernel-sysfs"
    if normalized == "sysfs-mouse":
        return "kernel-sysfs"
    if normalized.startswith("ite"):
        return "usb-userspace"
    return None


@contextmanager
def _disable_usb_scan_under_pytest_if_needed() -> Iterator[None]:
    did_override_usb_scan = False
    restore_disable_usb_scan: str | None = None

    if (
        os.environ.get("PYTEST_CURRENT_TEST")
        and os.environ.get("KEYRGB_ALLOW_HARDWARE") != "1"
        and os.environ.get("KEYRGB_HW_TESTS") != "1"
    ):
        restore_disable_usb_scan = os.environ.get("KEYRGB_DISABLE_USB_SCAN")
        os.environ["KEYRGB_DISABLE_USB_SCAN"] = "1"
        did_override_usb_scan = True

    try:
        yield
    finally:
        if did_override_usb_scan:
            if restore_disable_usb_scan is None:
                os.environ.pop("KEYRGB_DISABLE_USB_SCAN", None)
            else:
                os.environ["KEYRGB_DISABLE_USB_SCAN"] = restore_disable_usb_scan


def _probe_backend(backend: object) -> dict[str, Any]:
    try:
        probe_fn = getattr(backend, "probe", None)
        if callable(probe_fn):
            result = probe_fn()
            available = bool(getattr(result, "available", False))
            reason = str(getattr(result, "reason", ""))
            confidence = safe_int_attr(result, "confidence", default=0)
            identifiers = getattr(result, "identifiers", None)
        else:
            available = bool(getattr(backend, "is_available")())
            reason = "is_available"
            confidence = 50 if available else 0
            identifiers = None
    except Exception as exc:  # @quality-exception exception-transparency: backend probe execution is a best-effort diagnostics boundary
        _log_snapshot_boundary("Failed to probe backend during diagnostics collection", exc)
        available = False
        reason = f"probe exception: {exc}"
        confidence = 0
        identifiers = None

    entry: dict[str, Any] = {
        "name": getattr(backend, "name", backend.__class__.__name__),
        "available": available,
        "confidence": confidence,
        "reason": reason,
    }

    entry["priority"] = safe_int_attr(backend, "priority", default=0)

    try:
        entry["stability"] = stability_for_backend(backend).value
    except _BACKEND_METADATA_ERRORS:
        pass

    try:
        evidence = experimental_evidence_for_backend(backend)
        if evidence is not None:
            entry["experimental_evidence"] = evidence.value
    except _BACKEND_METADATA_ERRORS:
        pass

    try:
        selection_enabled, selection_reason = selection_allowed_for_backend(backend)
        entry["selection_enabled"] = bool(selection_enabled)
        if selection_reason:
            entry["selection_reason"] = selection_reason
    except _BACKEND_METADATA_ERRORS:
        pass

    tier = _tier_for_backend_name(str(entry.get("name") or ""))
    if tier is not None:
        entry["tier"] = tier
    provider = _provider_for_backend_name(str(entry.get("name") or ""))
    if provider is not None:
        entry["provider"] = provider

    if identifiers:
        try:
            entry["identifiers"] = dict(identifiers)
        except _IDENTIFIER_NORMALIZATION_ERRORS:
            pass

    return entry


def _selection_is_blocked_under_pytest() -> tuple[bool, str | None]:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False, None
    allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"
    if allow_hardware:
        return False, None
    return True, "selection disabled under pytest unless KEYRGB_ALLOW_HARDWARE=1"


def _collect_available_candidates(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_candidates: list[dict[str, Any]] = []
    for probe in probes:
        if not probe.get("available"):
            continue
        available_candidates.append(
            {
                "name": probe.get("name"),
                "confidence": probe.get("confidence"),
                "priority": probe.get("priority"),
                "tier": probe.get("tier"),
                "provider": probe.get("provider"),
                "stability": probe.get("stability"),
                "experimental_evidence": probe.get("experimental_evidence"),
                "reason": probe.get("reason"),
                "identifiers": probe.get("identifiers"),
            }
        )

    available_candidates.sort(
        key=lambda entry: (
            _coerce_sort_value(entry.get("confidence")),
            _coerce_sort_value(entry.get("priority")),
        ),
        reverse=True,
    )

    return available_candidates


def _iter_auxiliary_probe_backends() -> list[object]:
    try:
        from ...backends.sysfs_mouse.backend import SysfsMouseBackend

        return [SysfsMouseBackend()]
    except Exception as exc:  # @quality-exception exception-transparency: auxiliary diagnostics probe registration is a best-effort boundary and should not block the main snapshot
        _log_snapshot_boundary("Failed to register auxiliary diagnostics probe backends", exc)
        return []


def backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort)."""

    try:
        from ...backends.registry import iter_backends, select_backend
    except Exception as exc:  # @quality-exception exception-transparency: backend registry import is a best-effort diagnostics boundary
        _log_snapshot_boundary("Failed to import backend registry during diagnostics collection", exc)
        return {}

    probes: list[dict[str, Any]] = []
    with _disable_usb_scan_under_pytest_if_needed():
        for backend in iter_backends():
            probes.append(_probe_backend(backend))
        for backend in _iter_auxiliary_probe_backends():
            probes.append(_probe_backend(backend))

    requested = os.environ.get("KEYRGB_BACKEND") or "auto"

    selection_blocked, selection_blocked_reason = _selection_is_blocked_under_pytest()

    selected = None
    try:
        if not selection_blocked:
            selected_backend = select_backend()
            selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception as exc:  # @quality-exception exception-transparency: selected backend resolution is a best-effort diagnostics boundary
        _log_snapshot_boundary("Failed to resolve selected backend during diagnostics collection", exc)
        selected = None

    available_candidates = _collect_available_candidates(probes)
    guided_speed_probes = build_backend_speed_probe_plans(backends_snapshot={"selected": selected, "probes": probes})

    return {
        "selected": selected,
        "requested": requested,
        "probes": probes,
        "selection": {
            "policy": "highest confidence wins; priority is tie-breaker",
            "requested_effective": requested,
            "blocked": selection_blocked,
            "blocked_reason": selection_blocked_reason,
            "experimental_backends_enabled": bool(experimental_backends_enabled()),
            "disable_usb_scan": (os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1"),
        },
        "candidates_sorted": available_candidates,
        "guided_speed_probes": guided_speed_probes,
        "sysfs_led_candidates": sysfs_led_candidates_snapshot(),
        "sysfs_mouse_candidates": sysfs_mouse_candidates_snapshot(),
    }
