"""UX-04 guided setup integration: preflight evidence and gate (Tk-free).

Builds :class:`CalibrationPreflightEvidence` from cached sources only (the
tray snapshot or the already-selected backend/open ``kb``; never probing)
and evaluates the preflight gate with the standalone live-preview guard:
``LIVE_PREVIEW`` stands only when the tray-managed snapshot declares
``per_key``. Only the narrow ``OSError``/``RuntimeError``/``TypeError``/
``ValueError``/``AttributeError`` boundary is caught; unexpected exceptions
propagate.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

from keyrgb.core.backends.base import normalize_backend_capabilities

from ..model import KeymapValidation, validate_keymap_for_calibration_skip
from ..preflight import (
    CalibrationPreflightEvidence,
    CalibrationPreflightResult,
    PreflightMode,
    evaluate_calibration_preflight,
)
from . import integration_evidence as _evidence_module, integration_types as _types_module


def _backend_fallback_evidence(
    editor: object,
    hardware_module: object | None,
) -> tuple[object | None, str | None, tuple[int, int] | None, bool | None]:
    """Read cached backend/device evidence without probing or opening."""

    backend: object | None = None
    if hardware_module is None:
        try:
            from keyrgb.gui.perkey import hardware as live_hardware
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            return None, None, None, None
        hardware_module = live_hardware
    try:
        backend = cast(_types_module._SetupHardwareModule, hardware_module)._backend
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        backend = None
    capabilities: object | None = None
    backend_name: str | None = None
    dimensions: tuple[int, int] | None = None
    if backend is not None:
        typed_backend = cast(_types_module._SetupBackendProtocol, backend)
        try:
            capabilities = typed_backend.capabilities()
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            capabilities = None
        try:
            raw_name = typed_backend.name
            backend_name = str(raw_name).strip() or None if isinstance(raw_name, str) else None
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            backend_name = None
        try:
            dimensions = _types_module._validated_dimensions(typed_backend.dimensions())
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            dimensions = None
    has_writer: bool | None = None
    try:
        kb = getattr(editor, "kb", None)
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        kb = None
    if kb is not None:
        try:
            has_writer = bool(callable(getattr(kb, "set_key_colors", None)))
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            has_writer = None
    return capabilities, backend_name, dimensions, has_writer


def collect_preflight_evidence(
    editor: object,
    *,
    env: Mapping[str, str] | None = None,
    hardware_module: object | None = None,
    already_running: bool = False,
    policy_disabled: bool = False,
) -> CalibrationPreflightEvidence:
    """Build preflight evidence from cached sources only (no probing)."""

    env_map = dict(os.environ) if env is None else dict(env)
    tray_managed = _evidence_module.is_tray_managed(env_map)
    try:
        config = getattr(editor, "config", None)
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        config = None
    config_writable = _evidence_module.config_is_writable(config)
    view = _evidence_module._parse_snapshot_view(env_map)
    if view.present:
        return CalibrationPreflightEvidence(
            selected_capabilities=dict(view.capabilities or {}),
            backend_name=view.backend_name,
            dimensions=tuple(view.dimensions) if view.dimensions is not None else None,
            has_per_key_writer=None,
            already_running=bool(already_running),
            config_writable=config_writable,
            policy_disabled=bool(policy_disabled),
            tray_managed=tray_managed,
        )
    capabilities, backend_name, dimensions, has_writer = _backend_fallback_evidence(editor, hardware_module)
    return CalibrationPreflightEvidence(
        selected_capabilities=capabilities,
        backend_name=backend_name,
        dimensions=tuple(dimensions) if dimensions is not None else None,
        has_per_key_writer=has_writer,
        already_running=bool(already_running),
        config_writable=config_writable,
        policy_disabled=bool(policy_disabled),
        tray_managed=tray_managed,
    )


def resolve_setup_preflight(
    editor: object,
    *,
    env: Mapping[str, str] | None = None,
    hardware_module: object | None = None,
    already_running: bool = False,
    policy_disabled: bool = False,
) -> CalibrationPreflightResult:
    """Evaluate the preflight gate with the standalone live-preview guard.

    ``LIVE_PREVIEW`` stands only when the tray-managed snapshot declares
    ``per_key``; otherwise the verdict is re-derived from brightness-only
    capabilities so config-only messaging applies. Brightness-only evidence
    is never upgraded.
    """

    evidence = collect_preflight_evidence(
        editor,
        env=env,
        hardware_module=hardware_module,
        already_running=already_running,
        policy_disabled=policy_disabled,
    )
    result = evaluate_calibration_preflight(evidence)
    if result.mode is not PreflightMode.LIVE_PREVIEW:
        return result
    env_map = dict(os.environ) if env is None else dict(env)
    if _evidence_module.is_tray_managed(env_map) and _evidence_module.snapshot_declares_per_key(env_map):
        return result
    downgraded_caps = normalize_backend_capabilities(evidence.selected_capabilities)
    downgraded = replace(
        evidence,
        selected_capabilities={
            "brightness": bool(downgraded_caps.brightness),
            "per_key": False,
            "color": bool(downgraded_caps.color),
            "hardware_effects": bool(downgraded_caps.hardware_effects),
            "palette": bool(downgraded_caps.palette),
        },
    )
    result = evaluate_calibration_preflight(downgraded)
    return replace(
        result,
        message=(
            "live key flashing is unavailable when the editor is opened outside the running tray. "
            "You can continue config-only setup; open the editor from the tray to verify calibration live."
        ),
    )


def calibration_skip_validation(
    keymap: Mapping[str, object] | None,
    *,
    rows: int,
    cols: int,
) -> KeymapValidation:
    """Check whether a keymap may skip the calibration step (read-only)."""

    return validate_keymap_for_calibration_skip(keymap, rows=rows, cols=cols)
