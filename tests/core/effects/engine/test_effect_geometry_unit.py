from __future__ import annotations

from src.core.backends.base import BackendCapabilities
from src.core.effects.engine import EffectsEngine
from src.core.effects.matrix_layout import (
    REFERENCE_EFFECT_GEOMETRY,
    EffectGridGeometry,
    effect_geometry_from_dimensions,
    geometry_for_engine,
)
from src.core.effects.software import base as software_base


class _PerKeyBackend:
    def __init__(self, *, name: str, rows: int, cols: int) -> None:
        self.name = name
        self._rows = rows
        self._cols = cols

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            brightness=True,
            per_key=True,
            color=True,
            hardware_effects=False,
            palette=False,
        )

    def dimensions(self) -> tuple[int, int]:
        return self._rows, self._cols

    def effects(self) -> dict[str, object]:
        return {}

    def colors(self) -> dict[str, object]:
        return {}

    def get_device(self):
        raise FileNotFoundError("geometry unit tests do not open hardware")


class _UniformBackend:
    name = "uniform-test"

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            brightness=True,
            per_key=False,
            color=True,
            hardware_effects=False,
            palette=False,
        )

    def dimensions(self) -> tuple[int, int]:
        return (1, 1)

    def effects(self) -> dict[str, object]:
        return {}

    def colors(self) -> dict[str, object]:
        return {}

    def get_device(self):
        raise FileNotFoundError("geometry unit tests do not open hardware")


def test_effect_geometry_from_dimensions_uses_backend_matrix_when_per_key() -> None:
    geometry = effect_geometry_from_dimensions((7, 20), backend_name="ite8258_perkey_chassis", per_key=True)

    assert geometry == EffectGridGeometry(
        rows=7,
        cols=20,
        source="backend",
        backend_name="ite8258_perkey_chassis",
    )


def test_effect_geometry_from_dimensions_keeps_reference_for_non_per_key() -> None:
    geometry = effect_geometry_from_dimensions((1, 1), backend_name="sysfs-leds", per_key=False)

    assert geometry.source == "reference"
    assert geometry.rows == REFERENCE_EFFECT_GEOMETRY.rows
    assert geometry.cols == REFERENCE_EFFECT_GEOMETRY.cols


def test_engine_owns_backend_geometry_for_per_key_backend() -> None:
    engine = EffectsEngine(backend=_PerKeyBackend(name="ite8258_perkey_chassis", rows=7, cols=20))

    assert engine.effect_geometry.rows == 7
    assert engine.effect_geometry.cols == 20
    assert engine.effect_geometry.source == "backend"
    assert software_base.base_color_map(engine).keys() == {(row, col) for row in range(7) for col in range(20)}


def test_engine_keeps_reference_geometry_for_uniform_backend() -> None:
    engine = EffectsEngine(backend=_UniformBackend())

    assert engine.effect_geometry.source == "reference"
    assert engine.effect_geometry.rows == REFERENCE_EFFECT_GEOMETRY.rows
    assert engine.effect_geometry.cols == REFERENCE_EFFECT_GEOMETRY.cols


def test_engine_geometry_refreshes_on_backend_change() -> None:
    engine = EffectsEngine(backend=_PerKeyBackend(name="ite8910_perkey", rows=6, cols=20))
    assert engine.effect_geometry.cols == 20

    engine.set_backend(_PerKeyBackend(name="ite8291r3_perkey", rows=6, cols=21))

    assert geometry_for_engine(engine).cols == 21
    assert software_base.base_color_map(engine).keys() == {(row, col) for row in range(6) for col in range(21)}


def test_software_base_map_does_not_emit_out_of_range_cells_for_six_by_twenty() -> None:
    engine = EffectsEngine(backend=_PerKeyBackend(name="ite8910_perkey", rows=6, cols=20))
    engine.per_key_colors = {(0, 19): (1, 2, 3), (0, 20): (9, 9, 9)}

    color_map = software_base.base_color_map(engine)

    assert (0, 19) in color_map
    assert color_map[(0, 19)] == (1, 2, 3)
    assert (0, 20) not in color_map
    assert len(color_map) == 6 * 20
