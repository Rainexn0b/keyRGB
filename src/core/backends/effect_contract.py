"""Explicit contract for backend hardware-effect payload builders."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol


class UnsupportedHardwareEffectArgument(ValueError):
    """Raised when a builder receives a payload field it does not support."""

    def __init__(self, argument: str) -> None:
        self.argument = str(argument)
        super().__init__(f"'{self.argument}' attr is not needed by effect")


class HardwareEffectBuilderProtocol(Protocol):
    """Callable builder with explicit accepted payload fields."""

    accepted_kwargs: frozenset[str]

    def __call__(self, **kwargs: object) -> object: ...


@dataclass(frozen=True, slots=True)
class HardwareEffectBuilder:
    """Immutable metadata wrapper around a backend payload builder."""

    build: Callable[..., object]
    accepted_kwargs: frozenset[str]

    def __call__(self, **kwargs: object) -> object:
        unsupported = set(kwargs) - self.accepted_kwargs
        if unsupported:
            raise UnsupportedHardwareEffectArgument(min(unsupported))
        return self.build(**kwargs)


def hardware_effect_builder(
    build: Callable[..., object],
    *,
    accepted_kwargs: Iterable[str],
) -> HardwareEffectBuilder:
    """Attach an explicit accepted-field contract to ``build``."""

    return HardwareEffectBuilder(
        build=build,
        accepted_kwargs=frozenset(str(key) for key in accepted_kwargs),
    )
