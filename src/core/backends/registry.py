from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .base import KeyboardBackend, ProbeResult
from .exceptions import BackendError  # noqa: F401 – available for callers and future narrowing
from .policy import experimental_backends_enabled, selection_allowed_for_backend, stability_for_backend

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendSpec:
    name: str
    priority: int
    factory: Callable[[], KeyboardBackend]


def _default_specs() -> list[BackendSpec]:
    # Keep this list small and lazy-importing.
    from .asusctl import AsusctlAuraBackend
    from .ite8258 import Ite8258Backend
    from .ite8291 import Ite8291Backend
    from .ite8291_zones import Ite8291ZonesBackend
    from .ite8295_zones import Ite8295ZonesBackend
    from .ite8233 import Ite8233Backend
    from .ite8910 import Ite8910Backend
    from .ite8291r3 import Ite8291r3Backend
    from .ite8297 import Ite8297Backend
    from .sysfs import SysfsLedsBackend

    return [
        BackendSpec(
            name=AsusctlAuraBackend().name,
            priority=AsusctlAuraBackend().priority,
            factory=AsusctlAuraBackend,
        ),
        BackendSpec(
            name=Ite8291r3Backend().name,
            priority=Ite8291r3Backend().priority,
            factory=Ite8291r3Backend,
        ),
        BackendSpec(
            name=Ite8291Backend().name,
            priority=Ite8291Backend().priority,
            factory=Ite8291Backend,
        ),
        BackendSpec(
            name=Ite8258Backend().name,
            priority=Ite8258Backend().priority,
            factory=Ite8258Backend,
        ),
        BackendSpec(
            name=Ite8295ZonesBackend().name,
            priority=Ite8295ZonesBackend().priority,
            factory=Ite8295ZonesBackend,
        ),
        BackendSpec(
            name=Ite8291ZonesBackend().name,
            priority=Ite8291ZonesBackend().priority,
            factory=Ite8291ZonesBackend,
        ),
        BackendSpec(
            name=Ite8233Backend().name,
            priority=Ite8233Backend().priority,
            factory=Ite8233Backend,
        ),
        BackendSpec(
            name=Ite8910Backend().name,
            priority=Ite8910Backend().priority,
            factory=Ite8910Backend,
        ),
        BackendSpec(
            name=Ite8297Backend().name,
            priority=Ite8297Backend().priority,
            factory=Ite8297Backend,
        ),
        BackendSpec(
            name=SysfsLedsBackend().name,
            priority=SysfsLedsBackend().priority,
            factory=SysfsLedsBackend,
        ),
    ]


def iter_backends(*, specs: Optional[Iterable[BackendSpec]] = None) -> list[KeyboardBackend]:
    out: list[KeyboardBackend] = []
    for spec in list(specs) if specs is not None else _default_specs():
        try:
            out.append(spec.factory())
        except Exception:  # @quality-exception exception-transparency: backend factories are runtime plugin boundaries and auto iteration must skip broken implementations; device errors are now BackendError subclasses but raised in get_device(), not the factory constructor
            logger.exception("Failed to construct backend '%s'", spec.name)
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
        except Exception as exc:  # @quality-exception exception-transparency: backend probes are runtime hardware/plugin boundaries and selection must degrade to unavailable
            logger.exception("Backend probe failed for '%s'", backend.name)
            return ProbeResult(available=False, reason=f"probe exception: {exc}", confidence=0)

    try:
        ok = bool(backend.is_available())
        return ProbeResult(available=ok, reason="is_available", confidence=(50 if ok else 0))
    except Exception as exc:  # @quality-exception exception-transparency: is_available fallback is a runtime backend boundary and selection must degrade to unavailable
        logger.exception("Backend availability fallback failed for '%s'", backend.name)
        return ProbeResult(available=False, reason=f"is_available exception: {exc}", confidence=0)


def select_backend(
    *, requested: Optional[str] = None, specs: Optional[Iterable[BackendSpec]] = None
) -> Optional[KeyboardBackend]:
    """Select a backend.

    Order of precedence:
    - explicit `requested`
    - env `KEYRGB_BACKEND`
    - auto selection (highest confidence, then priority)

    Allowed values: backend name, or `auto`.
    Returns None if nothing is available.
    """

    # Safety: under pytest, never auto-select real hardware backends by default.
    # Unit tests that want to exercise selection logic should pass explicit `specs`.
    # Hardware smoke tests should opt-in via KEYRGB_ALLOW_HARDWARE=1 or KEYRGB_HW_TESTS=1.
    if specs is None and os.environ.get("PYTEST_CURRENT_TEST"):
        allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"
        if not allow_hardware:
            return None

    req = (requested or os.environ.get("KEYRGB_BACKEND") or "auto").strip().lower()
    backends = iter_backends(specs=specs)

    if req != "auto":
        for backend in backends:
            if backend.name.lower() == req:
                selectable, selection_reason = selection_allowed_for_backend(backend)
                if not selectable:
                    logger.debug(
                        "Backend '%s' requested but disabled by policy: %s",
                        backend.name,
                        selection_reason,
                    )
                    return None
                result = _probe_backend(backend)
                if not result.available:
                    logger.debug(
                        "Backend '%s' requested but unavailable: %s",
                        backend.name,
                        result.reason,
                    )
                    return None
                logger.debug("Backend '%s' selected (requested).", backend.name)
                return backend
        return None

    candidates: list[tuple[ProbeResult, KeyboardBackend]] = []
    for backend in backends:
        selectable, selection_reason = selection_allowed_for_backend(backend)
        if not selectable:
            logger.debug(
                "Backend policy: %s -> disabled (%s)",
                backend.name,
                selection_reason,
            )
            continue

        result = _probe_backend(backend)
        logger.debug(
            "Backend probe: %s -> stability=%s available=%s confidence=%s reason=%s experimental_enabled=%s",
            backend.name,
            stability_for_backend(backend).value,
            result.available,
            result.confidence,
            result.reason,
            experimental_backends_enabled(),
        )
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
