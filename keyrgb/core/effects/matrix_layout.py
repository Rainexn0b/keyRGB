"""Canonical effect-grid geometry.

Software effects, reactive rendering, fades, and tray-icon mosaics render on one
logical keyboard matrix owned by the effects engine at runtime.

The reference constants remain the fallback when no per-key backend geometry is
available. Live frame construction must read the engine snapshot rather than
assuming the historical 6x21 ITE matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal

from keyrgb.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS

GeometrySource = Literal["backend", "reference"]
Key = tuple[int, int]

_DIMENSION_COERCION_ERRORS = (OverflowError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class EffectGridGeometry:
    """One immutable effect-grid snapshot."""

    rows: int
    cols: int
    source: GeometrySource = "reference"
    backend_name: str | None = None

    @property
    def cell_count(self) -> int:
        return int(self.rows) * int(self.cols)


REFERENCE_EFFECT_GEOMETRY: Final[EffectGridGeometry] = EffectGridGeometry(
    rows=int(REFERENCE_MATRIX_ROWS),
    cols=int(REFERENCE_MATRIX_COLS),
    source="reference",
    backend_name=None,
)

# Compatibility aliases for the reference fallback. Runtime frame construction
# should prefer engine.effect_geometry / geometry_for_engine().
NUM_ROWS: Final[int] = REFERENCE_EFFECT_GEOMETRY.rows
NUM_COLS: Final[int] = REFERENCE_EFFECT_GEOMETRY.cols


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[call-overload]
    except _DIMENSION_COERCION_ERRORS:
        return None
    if number <= 0:
        return None
    return number


def reference_effect_geometry(*, backend_name: str | None = None) -> EffectGridGeometry:
    if backend_name is None:
        return REFERENCE_EFFECT_GEOMETRY
    return EffectGridGeometry(
        rows=REFERENCE_EFFECT_GEOMETRY.rows,
        cols=REFERENCE_EFFECT_GEOMETRY.cols,
        source="reference",
        backend_name=backend_name,
    )


def effect_geometry_from_dimensions(
    dimensions: object,
    *,
    backend_name: str | None = None,
    per_key: bool,
) -> EffectGridGeometry:
    """Build geometry from backend dimensions when per-key ownership is active."""

    if not per_key:
        return reference_effect_geometry(backend_name=backend_name)

    rows: object
    cols: object
    try:
        rows, cols = dimensions  # type: ignore[misc]
    except _DIMENSION_COERCION_ERRORS:
        return reference_effect_geometry(backend_name=backend_name)

    row_count = _positive_int(rows)
    col_count = _positive_int(cols)
    if row_count is None or col_count is None:
        return reference_effect_geometry(backend_name=backend_name)

    return EffectGridGeometry(
        rows=row_count,
        cols=col_count,
        source="backend",
        backend_name=backend_name,
    )


def geometry_for_engine(engine: object | None) -> EffectGridGeometry:
    """Return the engine-owned geometry snapshot, or the reference fallback."""

    if engine is None:
        return REFERENCE_EFFECT_GEOMETRY
    geometry = getattr(engine, "effect_geometry", None)
    if isinstance(geometry, EffectGridGeometry):
        return geometry
    return REFERENCE_EFFECT_GEOMETRY


@lru_cache(maxsize=32)
def all_keys_for_dimensions(rows: int, cols: int) -> tuple[Key, ...]:
    return tuple((row, col) for row in range(int(rows)) for col in range(int(cols)))


def all_keys_for(geometry: EffectGridGeometry) -> tuple[Key, ...]:
    return all_keys_for_dimensions(int(geometry.rows), int(geometry.cols))
