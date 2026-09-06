from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass

from .base import KeyboardBackend, ProbeResult
from .policies.backend_selection import (
    experimental_backends_enabled,
    selection_allowed_for_backend,
    stability_for_backend,
)

logger = logging.getLogger("keyrgb.core.backends.registry")


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


def _auto_selection_safety_tier(backend: KeyboardBackend) -> int:
    """Prefer usable kernel-backed control before direct userspace hardware I/O.

    Derives the safety tier from static metadata when available, falling back
    to a name-based heuristic for unknown / external backends.
    """
    from .registry import get_metadata_for_backend_name

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

    from .registry import _BACKEND_NAME_ALIASES, _probe_backend

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
