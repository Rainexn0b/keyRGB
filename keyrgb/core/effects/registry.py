"""Discover software and reactive effect registration markers."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

from keyrgb.core.effects.effect_contract import EffectKind, EffectRegistration

_MARKER_TOKEN = "EFFECT_REGISTRATION"
_DISCOVERY_PACKAGES = (
    "keyrgb.core.effects.software",
    "keyrgb.core.effects.reactive",
)

_discovered_registrations_cache: tuple[EffectRegistration, ...] | None = None


def _package_dir(package_name: str) -> Path:
    module = importlib.import_module(package_name)
    module_file = module.__file__
    if not module_file:
        raise RuntimeError(f"effect discovery package {package_name!r} has no file path")
    return Path(module_file).resolve().parent


def _module_declares_marker(path: Path) -> bool:
    try:
        return _MARKER_TOKEN in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _candidate_module_names(package_name: str) -> list[str]:
    package_dir = _package_dir(package_name)
    names: list[str] = []

    for child in sorted(package_dir.iterdir()):
        if child.name.startswith("__"):
            continue
        if child.is_file() and child.suffix == ".py":
            if _module_declares_marker(child):
                names.append(f"{package_name}.{child.stem}")
            continue
        if child.is_dir() and (child / "__init__.py").exists() and not child.name.startswith("_"):
            init_path = child / "__init__.py"
            if _module_declares_marker(init_path):
                names.append(f"{package_name}.{child.name}")
    return names


def _registrations_from_module(module_name: str) -> list[EffectRegistration]:
    module = importlib.import_module(module_name)
    found: list[EffectRegistration] = []

    single = getattr(module, "EFFECT_REGISTRATION", None)
    if isinstance(single, EffectRegistration):
        found.append(single)

    many = getattr(module, "EFFECT_REGISTRATIONS", None)
    if isinstance(many, (tuple, list)):
        found.extend(item for item in many if isinstance(item, EffectRegistration))

    return found


def _sorted_registrations(registrations: Iterable[EffectRegistration]) -> tuple[EffectRegistration, ...]:
    def sort_key(reg: EffectRegistration) -> tuple[int, int, str]:
        kind_rank = 0 if reg.kind is EffectKind.SOFTWARE else 1
        return (kind_rank, int(reg.menu_order), reg.name)

    return tuple(sorted(registrations, key=sort_key))


def discover_effect_registrations() -> tuple[EffectRegistration, ...]:
    """Return shipped software/reactive effect markers in catalog order."""

    global _discovered_registrations_cache
    if _discovered_registrations_cache is not None:
        return _discovered_registrations_cache

    by_name: dict[str, EffectRegistration] = {}
    owners: dict[str, str] = {}
    for package_name in _DISCOVERY_PACKAGES:
        for module_name in _candidate_module_names(package_name):
            for registration in _registrations_from_module(module_name):
                name = str(registration.name or "").strip().lower()
                if not name:
                    raise ValueError(f"effect registration in {module_name} has an empty name")
                previous = owners.get(name)
                if previous is not None:
                    raise ValueError(f"duplicate effect registration {name!r}: {previous} and {module_name}")
                owners[name] = module_name
                if name != registration.name:
                    registration = EffectRegistration(
                        name=name,
                        kind=registration.kind,
                        runner=registration.runner,
                        start_color=registration.start_color,
                        title=registration.title,
                        menu_order=registration.menu_order,
                    )
                by_name[name] = registration

    discovered = _sorted_registrations(by_name.values())
    _discovered_registrations_cache = discovered
    return discovered


def _invalidate_discovery_cache() -> None:
    """Reset the discovery cache (primarily for tests)."""

    global _discovered_registrations_cache
    _discovered_registrations_cache = None


def iter_effect_registrations(*, kind: EffectKind | None = None) -> tuple[EffectRegistration, ...]:
    registrations = discover_effect_registrations()
    if kind is None:
        return registrations
    return tuple(item for item in registrations if item.kind is kind)


def effect_names(*, kind: EffectKind) -> list[str]:
    return [item.name for item in iter_effect_registrations(kind=kind)]


def get_effect_registration(name: str) -> EffectRegistration | None:
    normalized = str(name or "").strip().lower()
    if not normalized:
        return None
    for item in discover_effect_registrations():
        if item.name == normalized:
            return item
    return None
