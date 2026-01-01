from __future__ import annotations

import os
from typing import Any


def backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort)."""

    try:
        # Diagnostics is a subpackage under src/core, so backends live one level up.
        from ..backends.registry import iter_backends, select_backend
    except Exception:
        return {}

    probes: list[dict[str, Any]] = []
    for backend in iter_backends():
        try:
            probe_fn = getattr(backend, "probe", None)
            if callable(probe_fn):
                result = probe_fn()
                available = bool(getattr(result, "available", False))
                reason = str(getattr(result, "reason", ""))
                confidence = int(getattr(result, "confidence", 0) or 0)
                identifiers = getattr(result, "identifiers", None)
            else:
                available = bool(backend.is_available())
                reason = "is_available"
                confidence = 50 if available else 0
                identifiers = None
        except Exception as exc:
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
        if identifiers:
            entry["identifiers"] = dict(identifiers)
        probes.append(entry)

    selected = None
    try:
        selected_backend = select_backend()
        selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception:
        selected = None

    return {
        "selected": selected,
        "requested": (os.environ.get("KEYRGB_BACKEND") or "auto"),
        "probes": probes,
    }
