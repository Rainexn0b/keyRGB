"""Auxiliary-route matching for named emulation."""

from __future__ import annotations

from keyrgb.core.secondary_device_routes import SecondaryDeviceRoute

from .spec import EmulationSpec, get_emulation_spec


def _canonical(value: object) -> str:
    return str(value or "").strip().lower()


def route_is_emulated(route: SecondaryDeviceRoute, spec: EmulationSpec | None = None) -> bool:
    """Return whether one secondary route should use an in-memory device."""

    active = spec if spec is not None else get_emulation_spec()
    if active is None:
        return False
    if active.all_auxiliary:
        return True
    backend_name = _canonical(route.backend_name)
    parent_name = _canonical(route.parent_backend_name)
    if backend_name in {_canonical(name) for name in active.auxiliary}:
        return True
    return bool(active.primary and parent_name == _canonical(active.primary))


def auxiliary_emulation_enabled() -> bool:
    """Return whether any secondary route will be emulated."""

    spec = get_emulation_spec()
    if spec is None:
        return False
    if spec.all_auxiliary or spec.auxiliary:
        return True
    if not spec.primary:
        return False
    from keyrgb.core.secondary_device_routes import iter_secondary_routes

    return any(_canonical(route.parent_backend_name) == _canonical(spec.primary) for route in iter_secondary_routes())


def emulation_availability_source(spec: EmulationSpec) -> str:
    return "simulation" if spec.source == "legacy_secondary_simulate" else "emulation"


def emulation_availability_reason(spec: EmulationSpec) -> str:
    if spec.source == "legacy_secondary_simulate":
        return "secondary-device simulation enabled"
    if spec.all_auxiliary:
        return "backend emulation enabled for all auxiliary routes"
    if spec.preset:
        return f"backend emulation enabled (preset:{spec.preset})"
    return "backend emulation enabled"
