"""Unit tests for the uniform-color derivation in keyrgb/core/lighting_layers.py."""

from __future__ import annotations

import pytest

from keyrgb.core.lighting_layers import (
    bucket_color_map_to_zones,
    color_map_for_geometry,
    uniform_color_from_per_key_map,
    zone_cells_for_column,
)


def test_empty_map_returns_none() -> None:
    assert uniform_color_from_per_key_map({}) is None
    assert uniform_color_from_per_key_map(None) is None


@pytest.mark.parametrize(
    "value",
    [
        "red",
        42,
        [1, 2, 3],
        (1, 2, 3),
        object(),
    ],
)
def test_non_mapping_returns_none(value: object) -> None:
    assert uniform_color_from_per_key_map(value) is None


def test_uniform_map_returns_that_color() -> None:
    assert uniform_color_from_per_key_map({(0, 0): (10, 20, 30)}) == (10, 20, 30)


def test_mixed_map_returns_channel_means() -> None:
    # Integer division per channel mirrors the zone-device fallback rendering.
    assert uniform_color_from_per_key_map({(0, 0): (10, 20, 30), (0, 1): (20, 31, 40)}) == (15, 25, 35)


def test_nested_tuples_are_accepted() -> None:
    assert uniform_color_from_per_key_map({(0, 0): ((10, 20, 30),)}) == (10, 20, 30)
    assert uniform_color_from_per_key_map({(0, 0): [[10, 20, 30]]}) == (10, 20, 30)


def test_malformed_entries_return_none() -> None:
    assert uniform_color_from_per_key_map({(0, 0): "red"}) is None
    assert uniform_color_from_per_key_map({(0, 0): (1, 2)}) is None


def test_bucket_color_map_to_zones_splits_columns() -> None:
    colors = {
        (0, 0): (10, 0, 0),
        (0, 1): (10, 0, 0),
        (0, 2): (0, 10, 0),
        (0, 3): (0, 10, 0),
    }

    assert bucket_color_map_to_zones(colors, zone_count=2, source_cols=4) == {
        (0, 0): (10, 0, 0),
        (0, 1): (0, 10, 0),
    }


def test_color_map_for_geometry_buckets_wide_maps_onto_zone_row() -> None:
    colors = {(0, 0): (1, 0, 0), (0, 10): (0, 1, 0), (0, 20): (0, 0, 1)}

    projected = color_map_for_geometry(colors, rows=1, cols=4, source_cols=21)

    assert projected is not None
    assert set(projected) <= {(0, 0), (0, 1), (0, 2), (0, 3)}


def test_zone_cells_for_column_covers_the_band() -> None:
    cells = zone_cells_for_column(num_rows=2, num_cols=4, zone_count=2, column=0)

    assert cells == ((0, 0), (0, 1), (1, 0), (1, 1))
