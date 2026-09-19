"""Primary-backend emulation wrapper and selection intercept."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from keyrgb.core.backends.base import (
    BackendCapabilities,
    BackendStability,
    ExperimentalEvidence,
    KeyboardBackend,
    ProbeResult,
    normalize_backend_stability,
    normalize_experimental_evidence,
)

from .contracts import contract_for_backend
from .devices import EmulatedKeyboardDevice, emulated_device_for_backend
from .spec import EmulationError, EmulationSpec, get_emulation_spec


class EmulatedPrimaryBackend:
    """In-memory stand-in that keeps the production backend name and contract."""

    emulated = True

    def __init__(
        self,
        *,
        name: str,
        priority: int,
        stability: BackendStability,
        experimental_evidence: ExperimentalEvidence | None,
        capabilities: BackendCapabilities,
        dimensions: tuple[int, int],
    ) -> None:
        self.name = name
        self.priority = priority
        self.stability: BackendStability | str = stability
        self.experimental_evidence: ExperimentalEvidence | str | None = experimental_evidence
        self._capabilities = capabilities
        self._dimensions = dimensions

    def is_available(self) -> bool:
        return True

    def probe(self) -> ProbeResult:
        return ProbeResult(
            available=True,
            reason="emulated",
            confidence=0,
            identifiers={"emulated": "1", "backend": self.name},
        )

    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def get_device(self) -> EmulatedKeyboardDevice:
        return emulated_device_for_backend(
            backend_name=self.name,
            capabilities=self._capabilities,
            dimensions=self._dimensions,
        )

    def dimensions(self) -> tuple[int, int]:
        return self._dimensions

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}


def make_emulated_primary_backend(name: str) -> EmulatedPrimaryBackend:
    from keyrgb.core.backends.registry import get_metadata_for_backend_name

    contract = contract_for_backend(name)
    metadata = get_metadata_for_backend_name(name)
    if metadata is None:
        raise EmulationError(f"KEYRGB_EMULATE primary {name!r} is not a registered backend")
    return EmulatedPrimaryBackend(
        name=metadata.name,
        priority=int(metadata.priority),
        stability=normalize_backend_stability(metadata.stability),
        experimental_evidence=normalize_experimental_evidence(metadata.experimental_evidence),
        capabilities=contract.capabilities,
        dimensions=contract.dimensions,
    )


def _requested_matches_primary(requested_effective: str, primary: str) -> bool:
    from keyrgb.core.backends.registry import resolve_backend_name

    if requested_effective == "auto":
        return True
    return resolve_backend_name(requested_effective) == primary


def build_emulated_selection_report(
    backends: Iterable[KeyboardBackend],
    *,
    requested_name: str,
    requested_effective: str,
    spec: EmulationSpec,
) -> Any:
    from keyrgb.core.backends._registry_selection import BackendProbeEvaluation, BackendSelectionReport

    if spec.primary is None:
        raise EmulationError("internal: emulated selection requires a PRIMARY")
    if not _requested_matches_primary(requested_effective, spec.primary):
        raise EmulationError(f"KEYRGB_BACKEND={requested_effective!r} does not match emulated PRIMARY {spec.primary!r}")

    wrapper = make_emulated_primary_backend(spec.primary)
    probe = wrapper.probe()
    evaluations: list[BackendProbeEvaluation] = []
    seen_primary = False
    for backend in backends:
        backend_name = backend.name.strip().lower()
        if backend_name == spec.primary:
            seen_primary = True
            evaluations.append(
                BackendProbeEvaluation(
                    backend=wrapper,
                    result=probe,
                    selection_enabled=True,
                    selection_reason=None,
                    auto_safety_tier=0,
                )
            )
            continue
        evaluations.append(
            BackendProbeEvaluation(
                backend=backend,
                result=None,
                selection_enabled=False,
                selection_reason="skipped: emulation active",
                auto_safety_tier=0,
            )
        )
    if not seen_primary:
        evaluations.insert(
            0,
            BackendProbeEvaluation(
                backend=wrapper,
                result=probe,
                selection_enabled=True,
                selection_reason=None,
                auto_safety_tier=0,
            ),
        )
    selected_eval = next(evaluation for evaluation in evaluations if evaluation.backend is wrapper)
    return BackendSelectionReport(
        requested=requested_name,
        requested_effective=requested_effective,
        evaluations=tuple(evaluations),
        candidates=(selected_eval,),
        selected=wrapper,
    )


def emulated_selection_report_or_none(
    backends: Iterable[KeyboardBackend],
    *,
    requested_name: str,
    requested_effective: str,
) -> Any | None:
    spec = get_emulation_spec()
    if spec is None or spec.primary is None:
        return None
    return build_emulated_selection_report(
        backends,
        requested_name=requested_name,
        requested_effective=requested_effective,
        spec=spec,
    )


def is_emulated_backend(backend: object | None) -> bool:
    return bool(getattr(backend, "emulated", False))
