"""Completion contract shared by lighting owners and power-event producers."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum


class LightingStatus(str, Enum):
    APPLIED = "applied"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    FAILED = "failed"


@dataclass(frozen=True)
class LightingResult:
    status: LightingStatus
    completion: Future[LightingResult] | None = None

    def __bool__(self) -> bool:
        return self.status is LightingStatus.APPLIED

    @property
    def settled(self) -> bool:
        """A policy block consumes the request; a failure or deferral does not."""
        return self.status in (LightingStatus.APPLIED, LightingStatus.BLOCKED)


APPLIED = LightingResult(LightingStatus.APPLIED)
BLOCKED = LightingResult(LightingStatus.BLOCKED)
DEFERRED = LightingResult(LightingStatus.DEFERRED)
FAILED = LightingResult(LightingStatus.FAILED)


def lighting_result(value: object) -> LightingResult:
    """Adapt historical bool/None callbacks at the public controller boundary."""
    if isinstance(value, LightingResult):
        return value
    return FAILED if value is False else APPLIED
