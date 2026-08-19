"""Sectioned config document over the flat settings mapping.

``ConfigDocument`` does not change the on-disk JSON schema. It owns the live
settings dict identity used by ``Config`` and exposes domain projections so
callers can reason about lighting, power, idle/display, scheduler, layout, and
app keys without treating the whole map as one bag.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .domains import ConfigDomain, project_domain, project_extras


@dataclass
class ConfigDocument:
    """Mutable settings document with domain-aware projections."""

    _values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> ConfigDocument:
        if not isinstance(raw, Mapping):
            return cls()
        return cls(_values=dict(raw))

    @classmethod
    def from_defaults(cls, defaults: Mapping[str, Any]) -> ConfigDocument:
        return cls(_values=deepcopy(dict(defaults)))

    @property
    def values(self) -> dict[str, Any]:
        """Live mutable settings mapping (identity preserved for accessors)."""

        return self._values

    def replace(self, values: MutableMapping[str, Any] | Mapping[str, Any]) -> None:
        """Replace the live mapping identity (reload / successful persist merge)."""

        self._values = dict(values) if not isinstance(values, dict) else values

    def copy_values(self) -> dict[str, Any]:
        return deepcopy(self._values)

    def section(self, domain: ConfigDomain) -> Mapping[str, object]:
        """Readonly projection of present keys owned by ``domain``."""

        return MappingProxyType(project_domain(self._values, domain))

    def extras(self) -> Mapping[str, object]:
        """Readonly projection of unknown keys retained for forward compatibility."""

        return MappingProxyType(project_extras(self._values))

    def section_dict(self, domain: ConfigDomain) -> dict[str, object]:
        """Detached mutable copy of a domain section."""

        return project_domain(self._values, domain)

    def extras_dict(self) -> dict[str, object]:
        """Detached mutable copy of unknown keys."""

        return project_extras(self._values)
