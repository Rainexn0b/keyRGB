from __future__ import annotations

import os

from .base import BackendStability, ExperimentalEvidence, normalize_backend_stability, normalize_experimental_evidence


def _truthy_text(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def experimental_backends_enabled() -> bool:
    raw = os.environ.get("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS")
    if raw is not None:
        return _truthy_text(raw)

    try:
        from src.core.config import Config

        return bool(Config().experimental_backends_enabled)
    except Exception:
        return False


def stability_for_backend(backend: object) -> BackendStability:
    return normalize_backend_stability(getattr(backend, "stability", BackendStability.VALIDATED))


def experimental_evidence_for_backend(backend: object) -> ExperimentalEvidence | None:
    return normalize_experimental_evidence(getattr(backend, "experimental_evidence", None))


def experimental_evidence_label(value: object) -> str | None:
    evidence = normalize_experimental_evidence(value)
    if evidence == ExperimentalEvidence.REVERSE_ENGINEERED:
        return "research-backed"
    if evidence == ExperimentalEvidence.SPECULATIVE:
        return "speculative"
    return None


def selection_allowed_for_backend(backend: object) -> tuple[bool, str | None]:
    stability = stability_for_backend(backend)

    if stability == BackendStability.VALIDATED:
        return True, None

    if stability == BackendStability.EXPERIMENTAL:
        if experimental_backends_enabled():
            return True, None
        return (
            False,
            "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        )

    return False, "dormant backend disabled"
