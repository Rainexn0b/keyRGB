from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .base import KeyboardBackend, ProbeResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendSpec:
    name: str
    priority: int
    factory: Callable[[], KeyboardBackend]


def _default_specs() -> list[BackendSpec]:
    # Keep this list small and lazy-importing.
    from .ite8291r3 import Ite8291r3Backend
    from .sysfs_leds import SysfsLedsBackend

    return [
        BackendSpec(name=Ite8291r3Backend().name, priority=Ite8291r3Backend().priority, factory=Ite8291r3Backend),
        BackendSpec(name=SysfsLedsBackend().name, priority=SysfsLedsBackend().priority, factory=SysfsLedsBackend),
    ]


def iter_backends(*, specs: Optional[Iterable[BackendSpec]] = None) -> list[KeyboardBackend]:
    out: list[KeyboardBackend] = []
    for spec in (list(specs) if specs is not None else _default_specs()):
        try:
            out.append(spec.factory())
        except Exception:
            continue
    return out


def _probe_backend(backend: KeyboardBackend) -> ProbeResult:
    """Probe a backend.

    Backends may implement `probe()` returning a ProbeResult. If not, we fall
    back to `is_available()` with a generic confidence score.
    """

    probe_fn = getattr(backend, "probe", None)
    if callable(probe_fn):
        try:
            result = probe_fn()
            if isinstance(result, ProbeResult):
                return result
        except Exception as exc:
            return ProbeResult(available=False, reason=f"probe exception: {exc}", confidence=0)

    try:
        ok = bool(backend.is_available())
        return ProbeResult(available=ok, reason="is_available", confidence=(50 if ok else 0))
    except Exception as exc:
        return ProbeResult(available=False, reason=f"is_available exception: {exc}", confidence=0)


def select_backend(*, requested: Optional[str] = None, specs: Optional[Iterable[BackendSpec]] = None) -> Optional[KeyboardBackend]:
    """Select a backend.

    Order of precedence:
    - explicit `requested`
    - env `KEYRGB_BACKEND`
    - auto selection (highest confidence, then priority)

    Allowed values: backend name, or `auto`.
    Returns None if nothing is available.
    """

    req = (requested or os.environ.get("KEYRGB_BACKEND") or "auto").strip().lower()
    backends = iter_backends(specs=specs)

    if req != "auto":
        for backend in backends:
            if backend.name.lower() == req:
                result = _probe_backend(backend)
                if not result.available:
                    logger.debug("Backend '%s' requested but unavailable: %s", backend.name, result.reason)
                    return None
                logger.debug("Backend '%s' selected (requested).", backend.name)
                return backend
        return None

    candidates: list[tuple[ProbeResult, KeyboardBackend]] = []
    for backend in backends:
        result = _probe_backend(backend)
        logger.debug("Backend probe: %s -> available=%s confidence=%s reason=%s", backend.name, result.available, result.confidence, result.reason)
        if result.available:
            candidates.append((result, backend))

    if not candidates:
        return None

    # Highest confidence wins; priority is a tiebreaker.
    candidates.sort(
        key=lambda pair: (
            int(getattr(pair[0], "confidence", 0)),
            int(getattr(pair[1], "priority", 0)),
        ),
        reverse=True,
    )
    return candidates[0][1]
