from __future__ import annotations

from types import SimpleNamespace

from keyrgb.core.effects.matrix_layout import EffectGridGeometry
from keyrgb.core.effects.reactive._runtime_inputs import project_slot_cells_for_engine


def test_project_slot_cells_buckets_canonical_keys_into_four_zones() -> None:
    engine = SimpleNamespace(
        backend_caps=SimpleNamespace(per_key=False, zoned=True),
        effect_geometry=EffectGridGeometry(rows=1, cols=4, source="backend", backend_name="zones-test"),
    )

    projected = project_slot_cells_for_engine(engine, ((0, 0), (2, 6), (3, 11), (4, 16), (5, 20)))

    assert projected == ((0, 0), (0, 1), (0, 2), (0, 3))


def test_project_slot_cells_leaves_per_key_coordinates_unchanged() -> None:
    cells = ((0, 0), (3, 10), (5, 20))
    engine = SimpleNamespace(backend_caps=SimpleNamespace(per_key=True, zoned=False))

    assert project_slot_cells_for_engine(engine, cells) is cells


def test_project_slot_cells_prefers_per_key_when_both_capabilities_are_set() -> None:
    cells = ((0, 0), (3, 10), (5, 20))
    engine = SimpleNamespace(backend_caps=SimpleNamespace(per_key=True, zoned=True))

    assert project_slot_cells_for_engine(engine, cells) is cells
