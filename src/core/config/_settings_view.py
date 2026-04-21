from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ConfigSettingsView(Mapping[str, object]):
    """Readonly typed boundary over config scalar/map settings."""

    _values: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        source = self._values
        if not isinstance(source, Mapping):
            object.__setattr__(self, "_values", MappingProxyType({}))
            return
        object.__setattr__(self, "_values", MappingProxyType(dict(source)))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object] | None) -> ConfigSettingsView:
        if not isinstance(raw, Mapping):
            return cls()
        return cls(_values=raw)

    def to_dict(self) -> dict[str, object]:
        return dict(self._values)

    def subset(self, keys: tuple[str, ...]) -> dict[str, object]:
        return {key: self._values[key] for key in keys if key in self._values}

    def read_int(self, key: str, default: int) -> int:
        value = self._values.get(key, default)
        try:
            return int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError, OverflowError):
            return int(default)

    def read_optional_int(self, key: str) -> int | None:
        value = self._values.get(key, None)
        if value is None:
            return None
        try:
            return int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError, OverflowError):
            return None

    def read_bool(self, key: str, default: bool) -> bool:
        value = self._values.get(key, default)
        try:
            return bool(value)
        except (RuntimeError, TypeError, ValueError):
            return bool(default)

    def read_normalized_str(self, key: str, default: str) -> str:
        value = self._values.get(key, default)
        fallback = str(default).strip().lower()
        try:
            normalized = str(value or default).strip().lower()
        except (RuntimeError, TypeError, ValueError):
            return fallback
        return normalized or fallback

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)
