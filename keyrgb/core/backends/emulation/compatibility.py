"""Compatibility rules for multi-backend emulation."""

from __future__ import annotations

from keyrgb.core.backends.base import BackendRole

from .contracts import EMULATED_CONTRACTS

PRESETS: dict[str, tuple[str, ...]] = {
    "beast-x30": ("ite8291_zones_clevo", "ite8291_none_chassis_lightbar_tongfang"),
    "legion-gen10": ("ite8258_perkey_chassis",),
    "perkey-clevo-bar": ("ite8291r3_perkey", "ite8233_none_chassis_lightbar_clevo"),
    "uniform": ("sysfs-leds",),
}

USB_IDENTITY_CONFLICT_GROUPS: tuple[frozenset[str], ...] = (
    frozenset(
        {
            "ite8291r3_perkey",
            "ite8291_perkey",
            "ite8291_zones_clevo",
        }
    ),
)


def _registry_roles() -> dict[str, BackendRole]:
    from keyrgb.core.backends.registry import discover_backend_registrations

    return {reg.metadata.name.strip().lower(): reg.metadata.role for reg in discover_backend_registrations()}


def _secondary_route_index() -> tuple[dict[str, str | None], set[str], set[str]]:
    from keyrgb.core.secondary_device_routes import iter_secondary_routes

    parents: dict[str, str | None] = {}
    standalone: set[str] = set()
    virtual_children: set[str] = set()
    for route in iter_secondary_routes():
        name = str(route.backend_name).strip().lower()
        parent = str(route.parent_backend_name).strip().lower() if route.parent_backend_name else None
        parents[name] = parent
        if parent:
            virtual_children.add(name)
        else:
            standalone.add(name)
    return parents, standalone, virtual_children


def known_emulation_names() -> set[str]:
    """Canonical names, aliases, and secondary-route identifiers that may appear in a spec."""

    from keyrgb.core.backends.registry import backend_name_aliases

    names = set(EMULATED_CONTRACTS)
    names.update(_registry_roles())
    aliases = backend_name_aliases()
    names.update(aliases)
    names.update(aliases.values())
    parents, standalone, virtual_children = _secondary_route_index()
    names.update(parents)
    names.update(standalone)
    names.update(virtual_children)
    names.update(parent for parent in parents.values() if parent)
    return {name.strip().lower() for name in names if name}


def resolve_emulation_name(token: str, *, known: set[str] | None = None) -> str:
    from keyrgb.core.backends.registry import resolve_backend_name

    from .spec import EmulationError

    raw = str(token or "").strip()
    if not raw:
        raise EmulationError("empty backend name in KEYRGB_EMULATE")
    resolved = resolve_backend_name(raw)
    allowed = known if known is not None else known_emulation_names()
    if resolved not in allowed:
        raise EmulationError(f"Unknown backend name in KEYRGB_EMULATE: {raw}")
    return resolved


def expand_preset(preset_id: str) -> tuple[str, ...]:
    from .spec import EmulationError

    normalized = str(preset_id or "").strip().lower()
    names = PRESETS.get(normalized)
    if names is None:
        raise EmulationError(f"Unknown KEYRGB_EMULATE preset: {preset_id}")
    return names


def _usb_identity_conflict(names: tuple[str, ...]) -> str | None:
    listed = set(names)
    for group in USB_IDENTITY_CONFLICT_GROUPS:
        overlap = listed & group
        if len(overlap) > 1:
            joined = ", ".join(sorted(overlap))
            return f"KEYRGB_EMULATE lists conflicting USB-identity backends: {joined}"
    return None


def classify_emulated_names(names: tuple[str, ...]) -> tuple[str | None, tuple[str, ...]]:
    """Split resolved names into at most one PRIMARY plus compatible AUXILIARY names."""

    from .spec import EmulationError

    conflict = _usb_identity_conflict(names)
    if conflict:
        raise EmulationError(conflict)

    roles = _registry_roles()
    _parents, standalone, virtual_children = _secondary_route_index()
    true_keyboards = {name for name, role in roles.items() if role is BackendRole.PRIMARY and name not in standalone}
    dual_role = {name for name, role in roles.items() if role is BackendRole.PRIMARY and name in standalone}
    auxiliary_only = {
        name
        for name in names
        if name in virtual_children
        or (name in standalone and name not in dual_role)
        or roles.get(name) is BackendRole.AUXILIARY
    }

    listed_keyboards = tuple(name for name in names if name in true_keyboards)
    listed_dual = tuple(name for name in names if name in dual_role)
    listed_aux = tuple(name for name in names if name in auxiliary_only)

    if len(listed_keyboards) > 1:
        joined = ", ".join(listed_keyboards)
        raise EmulationError(f"KEYRGB_EMULATE may include at most one PRIMARY backend; got {joined}")

    if listed_keyboards:
        primary = listed_keyboards[0]
        auxiliary = tuple(name for name in names if name != primary)
    elif len(listed_dual) > 1:
        joined = ", ".join(listed_dual)
        raise EmulationError(f"KEYRGB_EMULATE may include at most one PRIMARY backend; got {joined}")
    elif listed_dual:
        primary = listed_dual[0]
        auxiliary = tuple(name for name in names if name != primary)
    else:
        primary = None
        auxiliary = listed_aux if listed_aux else names

    unknown_primary_contract = primary is not None and primary not in EMULATED_CONTRACTS
    if unknown_primary_contract:
        raise EmulationError(f"KEYRGB_EMULATE primary {primary!r} has no emulated contract")

    for aux_name in auxiliary:
        parent = _parents.get(aux_name)
        if parent and parent != primary:
            raise EmulationError(f"KEYRGB_EMULATE auxiliary {aux_name!r} requires parent PRIMARY {parent!r}")

    return primary, auxiliary
