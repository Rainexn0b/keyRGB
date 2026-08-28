from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from .base import (
    BackendMetadata,
    BackendRegistration,
    BackendRole,
    KeyboardBackend,
    ProbeResult,
)
from .policies.backend_selection import (
    experimental_backends_enabled,
    selection_allowed_for_backend,
    stability_for_backend,
)

logger = logging.getLogger(__name__)
_BACKEND_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_T = TypeVar("_T")

# Map deprecated backend names to their canonical replacement. Users who set
# KEYRGB_BACKEND=<old_name> will transparently resolve to the canonical backend.
# See keyrgb/core/backends/README.md for the naming convention.
_BACKEND_NAME_ALIASES: dict[str, str] = {
    "ite8291r3": "ite8291r3_perkey",
    "ite8910": "ite8910_perkey",
    "ite8291": "ite8291_perkey",
    "ite8291-zones": "ite8291_zones_clevo",
    "ite8258": "ite8258_zones_lenovo_legion",
    "ite8258-chassis": "ite8258_perkey_chassis",
    "ite8295-zones": "ite8295_zones_lenovo_ideapad",
    "ite8233": "ite8233_none_chassis_lightbar_clevo",
    "ite8297": "ite8297_uniform",
    # Pre-rename canonical names (persisted in user configs / KEYRGB_BACKEND).
    "ite8291_zones": "ite8291_zones_clevo",
    "ite8258_zones": "ite8258_zones_lenovo_legion",
    "ite8258_chassis": "ite8258_perkey_chassis",
    "ite8258_perkey_chassis_logo_neon_vent_lenovo_legion": "ite8258_perkey_chassis",
    "ite8295_zones": "ite8295_zones_lenovo_ideapad",
    "ite8233_lightbar": "ite8233_none_chassis_lightbar_clevo",
}


@dataclass(frozen=True)
class BackendSpec:
    name: str
    priority: int
    factory: Callable[[], KeyboardBackend]


@dataclass(frozen=True)
class BackendProbeEvaluation:
    """One backend's probe and policy result in a selection report."""

    backend: KeyboardBackend
    result: ProbeResult | None
    selection_enabled: bool
    selection_reason: str | None
    auto_safety_tier: int


@dataclass(frozen=True)
class BackendSelectionReport:
    """Canonical evidence and outcome for one backend-selection decision."""

    requested: str
    requested_effective: str
    evaluations: tuple[BackendProbeEvaluation, ...]
    candidates: tuple[BackendProbeEvaluation, ...]
    selected: KeyboardBackend | None


def _spec_from_registration(reg: BackendRegistration) -> BackendSpec:
    """Build a registry spec from a ``BackendRegistration`` marker."""

    return BackendSpec(
        name=reg.metadata.name,
        priority=reg.metadata.priority,
        factory=reg.factory,
    )


# ---------------------------------------------------------------------------
# Deterministic discovery of backend packages exposing BACKEND_REGISTRATION
# ---------------------------------------------------------------------------

_DISCOVERY_SKIP_NAMES = frozenset({"policies"})
_discovered_registrations_cache: list[BackendRegistration] | None = None


def discover_backend_registrations() -> list[BackendRegistration]:
    """Scan backend sub-packages for ``BACKEND_REGISTRATION`` markers.

    Discovery is deterministic (sorted by directory name) and resilient to
    individual import failures: packages that cannot be imported or that do
    not expose a ``BACKEND_REGISTRATION`` marker are silently skipped.
    """
    global _discovered_registrations_cache
    if _discovered_registrations_cache is not None:
        return list(_discovered_registrations_cache)

    backend_dir = Path(__file__).parent
    registrations: list[BackendRegistration] = []

    for child in sorted(backend_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name in _DISCOVERY_SKIP_NAMES:
            continue
        if not (child / "__init__.py").exists():
            continue

        mod_name = f"keyrgb.core.backends.{child.name}"
        try:
            mod = importlib.import_module(mod_name)
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("Skipping backend package %s: import failed: %s", mod_name, exc)
            continue

        reg = getattr(mod, "BACKEND_REGISTRATION", None)
        if isinstance(reg, BackendRegistration):
            registrations.append(reg)

    _discovered_registrations_cache = registrations
    return list(registrations)


def _invalidate_discovery_cache() -> None:
    """Reset the discovery cache (primarily for tests)."""
    global _discovered_registrations_cache
    _discovered_registrations_cache = None


def get_metadata_for_backend_name(name: str) -> BackendMetadata | None:
    """Look up static metadata by canonical backend name."""
    normalized = (name or "").strip().lower()
    for reg in discover_backend_registrations():
        if reg.metadata.name.strip().lower() == normalized:
            return reg.metadata
    return None


def _run_recoverable_backend_boundary(
    action: Callable[[], _T],
    *,
    backend_name: str,
    log_message: str,
    on_recoverable: Callable[[Exception], _T],
) -> _T:
    try:
        return action()
    except _BACKEND_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: backend construction and availability probing cross runtime plugin/hardware boundaries; recoverable runtime failures must be logged and degraded while unexpected defects still propagate
        logger.exception(log_message, backend_name)
        return on_recoverable(exc)


def _unavailable_probe_result(boundary: str, exc: Exception) -> ProbeResult:
    return ProbeResult(available=False, reason=f"{boundary} exception: {exc}", confidence=0)


def _default_specs() -> list[BackendSpec]:
    """Return specs for all PRIMARY built-in backends via marker discovery."""
    specs = [
        _spec_from_registration(reg)
        for reg in discover_backend_registrations()
        if reg.metadata.role is BackendRole.PRIMARY
    ]
    specs.sort(key=lambda spec: (-int(spec.priority), spec.name))
    return specs


def iter_auxiliary_specs() -> list[BackendSpec]:
    """Return specs for all AUXILIARY built-in backends via marker discovery.

    Auxiliary backends (e.g. ``sysfs-mouse``) are excluded from primary
    auto-selection but remain visible in diagnostics and secondary-device
    workflows.
    """
    return [
        _spec_from_registration(reg)
        for reg in discover_backend_registrations()
        if reg.metadata.role is BackendRole.AUXILIARY
    ]


def iter_backends(*, specs: Iterable[BackendSpec] | None = None) -> list[KeyboardBackend]:
    out: list[KeyboardBackend] = []
    for spec in list(specs) if specs is not None else _default_specs():
        backend = _run_recoverable_backend_boundary(
            spec.factory,
            backend_name=spec.name,
            log_message="Failed to construct backend '%s'",
            on_recoverable=lambda _exc: None,
        )
        if backend is not None:
            out.append(backend)
    return out


def _probe_backend(backend: KeyboardBackend) -> ProbeResult:
    """Probe a backend.

    Backends may implement probe() returning a ProbeResult. If not, we fall
    back to is_available() with a generic confidence score.
    """

    probe_fn = getattr(backend, "probe", None)
    if callable(probe_fn):
        result = _run_recoverable_backend_boundary(
            probe_fn,
            backend_name=backend.name,
            log_message="Backend probe failed for '%s'",
            on_recoverable=lambda exc: _unavailable_probe_result("probe", exc),
        )
        if isinstance(result, ProbeResult):
            return result

    def _availability_result() -> ProbeResult:
        ok = bool(backend.is_available())
        return ProbeResult(available=ok, reason="is_available", confidence=(50 if ok else 0))

    return _run_recoverable_backend_boundary(
        _availability_result,
        backend_name=backend.name,
        log_message="Backend availability fallback failed for '%s'",
        on_recoverable=lambda exc: _unavailable_probe_result("is_available", exc),
    )


def _auto_selection_safety_tier(backend: KeyboardBackend) -> int:
    """Prefer usable kernel-backed control before direct userspace hardware I/O.

    Derives the safety tier from static metadata when available, falling back
    to a name-based heuristic for unknown / external backends.
    """
    meta = get_metadata_for_backend_name(backend.name)
    if meta is not None:
        return meta.auto_safety_tier()
    # Fallback: kernel-style names are treated as preferred.
    return 1 if backend.name.strip().lower() == "sysfs-leds" else 0


def build_backend_selection_report(
    backends: Iterable[KeyboardBackend],
    *,
    requested: str | None = None,
    probe_all: bool = False,
) -> BackendSelectionReport:
    """Probe and rank backends once using the runtime selection policy.

    Runtime explicit selection probes only the requested backend. Diagnostics
    passes ``probe_all=True`` so unavailable and policy-disabled backends remain
    visible without independently reimplementing selection or probing.
    """

    requested_name = (requested or os.environ.get("KEYRGB_BACKEND") or "auto").strip().lower()
    requested_effective = _BACKEND_NAME_ALIASES.get(requested_name, requested_name)
    evaluations: list[BackendProbeEvaluation] = []

    for backend in backends:
        selection_enabled, selection_reason = selection_allowed_for_backend(backend)
        backend_name = backend.name.strip().lower()
        should_probe = probe_all or (
            selection_enabled and (requested_effective == "auto" or backend_name == requested_effective)
        )
        result = _probe_backend(backend) if should_probe else None
        evaluation = BackendProbeEvaluation(
            backend=backend,
            result=result,
            selection_enabled=selection_enabled,
            selection_reason=selection_reason,
            auto_safety_tier=_auto_selection_safety_tier(backend),
        )
        evaluations.append(evaluation)

        if result is not None:
            logger.debug(
                "Backend probe: %s -> stability=%s available=%s confidence=%s reason=%s "
                "experimental_enabled=%s selection_enabled=%s",
                backend.name,
                stability_for_backend(backend).value,
                result.available,
                result.confidence,
                result.reason,
                experimental_backends_enabled(),
                selection_enabled,
            )

    candidates = [
        evaluation
        for evaluation in evaluations
        if evaluation.selection_enabled and evaluation.result is not None and evaluation.result.available
    ]
    candidates.sort(
        key=lambda evaluation: (
            evaluation.auto_safety_tier,
            int(getattr(evaluation.result, "confidence", 0)),
            int(getattr(evaluation.backend, "priority", 0)),
        ),
        reverse=True,
    )

    selected: KeyboardBackend | None = None
    if requested_effective == "auto":
        if candidates:
            selected = candidates[0].backend
    else:
        selected = next(
            (
                evaluation.backend
                for evaluation in evaluations
                if evaluation.backend.name.strip().lower() == requested_effective
                and evaluation.selection_enabled
                and evaluation.result is not None
                and evaluation.result.available
            ),
            None,
        )

    return BackendSelectionReport(
        requested=requested_name,
        requested_effective=requested_effective,
        evaluations=tuple(evaluations),
        candidates=tuple(candidates),
        selected=selected,
    )


def select_backend(
    *, requested: str | None = None, specs: Iterable[BackendSpec] | None = None
) -> KeyboardBackend | None:
    """Select a backend.

    Order of precedence:
    - explicit `requested`
    - env `KEYRGB_BACKEND`
    - auto selection (kernel/sysfs safety tier, then confidence and priority)

    Allowed values: backend name, alias, or `auto`.
    Returns None if nothing is available.
    """

    # Safety: under pytest, never auto-select real hardware backends by default.
    # Unit tests that want to exercise selection logic should pass explicit `specs`.
    # Hardware smoke tests should opt-in via KEYRGB_ALLOW_HARDWARE=1 or KEYRGB_HW_TESTS=1.
    if specs is None and os.environ.get("PYTEST_CURRENT_TEST"):
        allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"
        if not allow_hardware:
            return None

    backends = iter_backends(specs=specs)
    report = build_backend_selection_report(backends, requested=requested)
    if report.selected is not None:
        logger.debug("Backend '%s' selected (%s).", report.selected.name, report.requested_effective)
    return report.selected
