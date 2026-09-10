"""UX-04 calibration preflight: pure capability-based gate.

This module decides whether the guided calibration workflow may offer a live
preview, config-only editing, or nothing at all. It is intentionally pure and
deterministic:

* Inputs are injected cached evidence only (see
  :class:`CalibrationPreflightEvidence`). This module never selects, probes,
  or opens hardware, never imports the tray, and never touches the
  filesystem, environment, or diagnostics collection.
* Capability evidence (a ``BackendCapabilities`` instance, a ``Mapping``, or
  any attribute-bearing snapshot) is consumed exclusively through the core
  ``normalize_backend_capabilities`` normalizer, which fails closed: missing
  or malformed fields normalize to ``False``.
* Brightness-only / sysfs backends (``per_key`` False) are never treated as
  per-key capable.
* Tray-managed config-mediated preview still requires the injected selected
  capabilities to declare ``per_key`` (plus a per-key writer when writer
  evidence is provided) for ``LIVE_PREVIEW``; otherwise it degrades to
  ``CONFIG_ONLY``. The ``tray_managed`` flag is informational only and never
  upgrades a non-per-key backend to live preview.
* When writer evidence is provided (``has_per_key_writer`` is not ``None``),
  live preview additionally requires it, mirroring the
  ``supports_per_key_output`` contract (declared capability plus an
  operational per-key writer) without opening any device here.

Conservative contract (first match wins):

* ``BLOCKED``: ``CONFIG_UNWRITABLE`` and ``POLICY_DISABLED`` only.
  ``CONFIG_UNWRITABLE`` blocks because the workflow cannot persist any setup
  work; ``POLICY_DISABLED`` blocks because calibration is administratively
  prohibited, so proceeding even config-only would violate policy.
* ``CONFIG_ONLY`` (safe degradation: no hardware writes and no live key
  flashing, the user can still edit layout/optional state and may skip
  calibration when an existing keymap validates): ``ALREADY_RUNNING``,
  ``NO_BACKEND``, ``DISCONNECTED``, ``PERMISSION``, ``BUSY``,
  ``UNSUPPORTED_BACKEND``. ``ALREADY_RUNNING`` degrades rather than blocks
  because setup editing itself claims no hardware lock; only launching a
  second calibrator stays unavailable until the other session closes.
* ``LIVE_PREVIEW``: ``OK`` only.

Priority order: ``CONFIG_UNWRITABLE`` > ``POLICY_DISABLED`` >
``ALREADY_RUNNING`` > ``NO_BACKEND`` > ``DISCONNECTED`` > ``PERMISSION`` >
``BUSY`` > ``UNSUPPORTED_BACKEND`` > ``OK``.

Every ``CONFIG_ONLY`` message explicitly states that live key flashing is
unavailable (and unverified where no live evidence exists), per the approved
no-live-flash warning.

Button contract:

* ``offer_retry`` is set for transient states where re-collecting evidence or
  retrying the operation may succeed (already-running, config-unwritable,
  no-backend, disconnected, permission, busy). It is not set for ``OK``
  (nothing to retry), ``POLICY_DISABLED`` (retry cannot help), or
  ``UNSUPPORTED_BACKEND`` (re-probing the same backend cannot add per-key
  support).* ``offer_continue_config_only`` is set exactly for ``CONFIG_ONLY`` results.
* ``offer_support`` is set where the message names a system cause the user
  may need help diagnosing (config, policy, no-backend, disconnected,
  permission, busy, unsupported-backend).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS

__all__ = [
    "CalibrationPreflightEvidence",
    "CalibrationPreflightResult",
    "PreflightMode",
    "PreflightReason",
    "evaluate_calibration_preflight",
]


class PreflightMode(str, Enum):
    """Calibration workflow mode decided by the preflight gate."""

    LIVE_PREVIEW = "live_preview"
    CONFIG_ONLY = "config_only"
    BLOCKED = "blocked"


class PreflightReason(str, Enum):
    """Machine-readable reason for the preflight decision."""

    OK = "ok"
    ALREADY_RUNNING = "already_running"
    CONFIG_UNWRITABLE = "config_unwritable"
    POLICY_DISABLED = "policy_disabled"
    NO_BACKEND = "no_backend"
    DISCONNECTED = "disconnected"
    PERMISSION = "permission"
    BUSY = "busy"
    UNSUPPORTED_BACKEND = "unsupported_backend"


@dataclass(frozen=True)
class CalibrationPreflightEvidence:
    """Injected cached evidence for one preflight evaluation.

    All fields are caller-provided snapshots; nothing here is probed or
    collected. ``selected_capabilities`` accepts a ``BackendCapabilities``
    instance, a ``Mapping`` with capability keys, or ``None`` when no backend
    was selected. ``dimensions`` accepts a ``(rows, cols)`` pair or ``None``.
    ``has_per_key_writer`` records whether a per-key writer method exists on
    the cached device snapshot, or ``None`` when that evidence was not
    collected (in which case only declared capabilities gate live preview).
    """

    selected_capabilities: object | None = None
    backend_name: str | None = None
    dimensions: object | None = None
    has_per_key_writer: bool | None = None
    already_running: bool = False
    config_writable: bool = True
    policy_disabled: bool = False
    permission_denied: bool = False
    device_busy: bool = False
    device_disconnected: bool = False
    tray_managed: bool = False


@dataclass(frozen=True)
class CalibrationPreflightResult:
    """Outcome of :func:`evaluate_calibration_preflight`."""

    mode: PreflightMode
    reason: PreflightReason
    backend_name: str
    rows: int
    cols: int
    message: str
    offer_retry: bool
    offer_continue_config_only: bool
    offer_support: bool


_UNKNOWN_BACKEND_NAME = "unknown backend"
_MIN_DIMENSION = 1
_MAX_DIMENSION = 64


def _resolve_backend_name(value: object | None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _UNKNOWN_BACKEND_NAME


def _resolve_dimensions(value: object | None) -> tuple[int, int]:
    """Return validated ``(rows, cols)`` or the reference fallback."""
    pair: object = value
    if isinstance(pair, list):
        pair = tuple(pair)
    if (
        isinstance(pair, tuple)
        and len(pair) == 2
        and all(type(item) is int for item in pair)
        and all(_MIN_DIMENSION <= item <= _MAX_DIMENSION for item in pair)
    ):
        rows, cols = pair
        return int(rows), int(cols)
    return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS


def _writer_satisfied(has_per_key_writer: bool | None) -> bool:
    """Require the per-key writer only when that evidence was collected."""
    if has_per_key_writer is None:
        return True
    return bool(has_per_key_writer)


def _message_for(reason: PreflightReason, backend_name: str, rows: int, cols: int) -> str:
    if reason is PreflightReason.OK:
        return f"Live calibration preview is available on {backend_name} ({rows}x{cols})."
    if reason is PreflightReason.ALREADY_RUNNING:
        return (
            "Another calibration session is already running, so live key flashing is unavailable. "
            "You can continue config-only setup (a second calibrator cannot be launched); "
            "close the other session, then choose Retry."
        )
    if reason is PreflightReason.CONFIG_UNWRITABLE:
        return "Calibration config is not writable. Fix config permissions, then choose Retry."
    if reason is PreflightReason.POLICY_DISABLED:
        return "Calibration is disabled by policy. Contact your administrator or support."
    if reason is PreflightReason.NO_BACKEND:
        return (
            "No keyboard backend was detected, so live key flashing is unavailable and unverified. "
            "You can continue config-only setup; reconnect the keyboard, then choose Retry."
        )
    if reason is PreflightReason.DISCONNECTED:
        return (
            "The keyboard is disconnected, so live key flashing is unavailable. "
            "You can continue config-only setup; reconnect it, then choose Retry."
        )
    if reason is PreflightReason.PERMISSION:
        return (
            "Keyboard access was denied (permissions), so live key flashing is unavailable and unverified. "
            "You can continue config-only, or fix device permissions and choose Retry."
        )
    if reason is PreflightReason.BUSY:
        return (
            "The keyboard is busy (another tool may hold it), so live key flashing is unavailable and unverified. "
            "You can continue config-only, close the other tool, then choose Retry."
        )
    return (
        f"{backend_name} does not support per-key lighting "
        "(brightness-only or uniform color), so live key flashing is unavailable. "
        "You can continue with config-only editing."
    )


def evaluate_calibration_preflight(evidence: CalibrationPreflightEvidence) -> CalibrationPreflightResult:
    """Evaluate injected evidence and return a deterministic preflight result."""
    backend_name = _resolve_backend_name(evidence.backend_name)
    rows, cols = _resolve_dimensions(evidence.dimensions)

    if not evidence.config_writable:
        reason = PreflightReason.CONFIG_UNWRITABLE
        mode = PreflightMode.BLOCKED
        offer_retry, offer_config_only, offer_support = True, False, True
    elif evidence.policy_disabled:
        reason = PreflightReason.POLICY_DISABLED
        mode = PreflightMode.BLOCKED
        offer_retry, offer_config_only, offer_support = False, False, True
    elif evidence.already_running:
        reason = PreflightReason.ALREADY_RUNNING
        mode = PreflightMode.CONFIG_ONLY
        offer_retry, offer_config_only, offer_support = True, True, True
    elif evidence.selected_capabilities is None:
        reason = PreflightReason.NO_BACKEND
        mode = PreflightMode.CONFIG_ONLY
        offer_retry, offer_config_only, offer_support = True, True, True
    elif evidence.device_disconnected:
        reason = PreflightReason.DISCONNECTED
        mode = PreflightMode.CONFIG_ONLY
        offer_retry, offer_config_only, offer_support = True, True, True
    elif evidence.permission_denied:
        reason = PreflightReason.PERMISSION
        mode = PreflightMode.CONFIG_ONLY
        offer_retry, offer_config_only, offer_support = True, True, True
    elif evidence.device_busy:
        reason = PreflightReason.BUSY
        mode = PreflightMode.CONFIG_ONLY
        offer_retry, offer_config_only, offer_support = True, True, True
    else:
        caps = normalize_backend_capabilities(evidence.selected_capabilities)
        if caps.per_key and _writer_satisfied(evidence.has_per_key_writer):
            reason = PreflightReason.OK
            mode = PreflightMode.LIVE_PREVIEW
            offer_retry, offer_config_only, offer_support = False, False, False
        else:
            reason = PreflightReason.UNSUPPORTED_BACKEND
            mode = PreflightMode.CONFIG_ONLY
            offer_retry, offer_config_only, offer_support = False, True, True

    return CalibrationPreflightResult(
        mode=mode,
        reason=reason,
        backend_name=backend_name,
        rows=rows,
        cols=cols,
        message=_message_for(reason, backend_name, rows, cols),
        offer_retry=offer_retry,
        offer_continue_config_only=offer_config_only,
        offer_support=offer_support,
    )
