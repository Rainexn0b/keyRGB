from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkerBaseline:
    counts: dict[str, int]
    gated_markers: set[str]
