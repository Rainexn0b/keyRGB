"""Physical-controller identity for shared backend state."""

from __future__ import annotations


def controller_identity(*, backend_name: str, hidraw: object | None = None) -> str:
    """Return a stable shared-state key for one physical controller.

    Backend name alone is too coarse when two identical devices are present.
    When a hidraw node is known it is included; otherwise the key stays the
    backend name so single-device and test paths keep sharing keyboard/zone
    state on one controller.
    """

    name = str(backend_name or "").strip() or "unknown"
    node = str(hidraw or "").strip()
    return f"{name}:{node}" if node else name
