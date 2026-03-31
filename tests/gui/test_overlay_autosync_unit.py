from __future__ import annotations

import pytest

from src.core.resources.layout import KeyDef
from src.gui.perkey.overlay.autosync import (
    _apply_global_factory,
    _apply_per_key,
    _build_items,
    _cluster_sorted,
    _median,
    _row_and_col_thresholds,
    _snap_cols,
    _snap_rows,
    _sync_similar_sizes,
    auto_sync_per_key_overlays,
)


def _key(key_id: str, rect: tuple[int, int, int, int]) -> KeyDef:
    return KeyDef(key_id=key_id, label=key_id.upper(), rect=rect)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([7.0, 1.0, 3.0], 3.0),
        ([8.0, 2.0, 6.0, 4.0], 5.0),
    ],
)
def test_median_handles_odd_and_even_inputs(values: list[float], expected: float) -> None:
    assert _median(values) == pytest.approx(expected)


def test_apply_global_factory_returns_identity_when_layout_has_no_tweaks() -> None:
    apply_global = _apply_global_factory(layout_tweaks={}, base_image_size=(100, 100))

    assert apply_global(10.0, 20.0, 30.0, 40.0) == pytest.approx((10.0, 20.0, 30.0, 40.0))


def test_apply_global_factory_applies_scale_around_image_center_then_offsets() -> None:
    apply_global = _apply_global_factory(
        layout_tweaks={"dx": 5.0, "dy": -3.0, "sx": 2.0, "sy": 0.5},
        base_image_size=(100, 100),
    )

    assert apply_global(10.0, 20.0, 30.0, 40.0) == pytest.approx((-25.0, 32.0, 60.0, 20.0))


def test_apply_per_key_returns_global_geometry_when_key_has_no_tweaks() -> None:
    result = _apply_per_key(
        key_id="esc",
        gx=10.0,
        gy=20.0,
        gw=30.0,
        gh=40.0,
        per_key_layout_tweaks={},
    )

    assert result == pytest.approx((10.0, 20.0, 30.0, 40.0, 25.0, 40.0, {}), abs=1e-9)


def test_apply_per_key_applies_per_key_offsets_and_scale_around_key_center() -> None:
    result = _apply_per_key(
        key_id="enter",
        gx=5.0,
        gy=10.0,
        gw=10.0,
        gh=20.0,
        per_key_layout_tweaks={"enter": {"dx": 2.0, "dy": -3.0, "sx": 1.5, "sy": 0.5}},
    )

    x, y, w, h, cx, cy, tweaks = result
    assert (x, y, w, h, cx, cy) == pytest.approx((4.5, 12.0, 15.0, 10.0, 12.0, 17.0))
    assert tweaks == {"dx": 2.0, "dy": -3.0, "sx": 1.5, "sy": 0.5}


def test_build_items_maps_key_defs_to_expected_overlay_dicts() -> None:
    keys = [_key("a", (10, 20, 30, 18)), _key("b", (40, 50, 20, 10))]
    apply_global = _apply_global_factory(
        layout_tweaks={"dx": 2.0, "dy": -1.0},
        base_image_size=(100, 100),
    )

    items = _build_items(
        keys=keys,
        apply_global=apply_global,
        per_key_layout_tweaks={"b": {"dx": 3.0, "sx": 1.5, "sy": 0.5}},
    )

    assert items[0] == {
        "key_id": "a",
        "gx": 12.0,
        "gy": 19.0,
        "gw": 30.0,
        "gh": 18.0,
        "x": 12.0,
        "y": 19.0,
        "w": 30.0,
        "h": 18.0,
        "cx": 27.0,
        "cy": 28.0,
        "kt": {},
    }
    assert items[1]["key_id"] == "b"
    assert items[1]["gx"] == pytest.approx(42.0)
    assert items[1]["gy"] == pytest.approx(49.0)
    assert items[1]["gw"] == pytest.approx(20.0)
    assert items[1]["gh"] == pytest.approx(10.0)
    assert items[1]["x"] == pytest.approx(40.0)
    assert items[1]["y"] == pytest.approx(51.5)
    assert items[1]["w"] == pytest.approx(30.0)
    assert items[1]["h"] == pytest.approx(5.0)
    assert items[1]["cx"] == pytest.approx(55.0)
    assert items[1]["cy"] == pytest.approx(54.0)
    assert items[1]["kt"] == {"dx": 3.0, "sx": 1.5, "sy": 0.5}


def test_cluster_sorted_keeps_values_on_threshold_boundary_in_same_group() -> None:
    values = [
        {"key_id": "a", "cy": 4.1},
        {"key_id": "b", "cy": 0.0},
        {"key_id": "c", "cy": 6.1},
        {"key_id": "d", "cy": 2.0},
    ]

    groups = _cluster_sorted(values, "cy", thresh=2.0)

    assert [[item["key_id"] for item in group] for group in groups] == [["b", "d"], ["a", "c"]]


def test_sync_similar_sizes_normalizes_near_equal_groups_and_skips_singletons_and_divergent_groups() -> None:
    items = [
        {"key_id": "a", "gw": 20.0, "gh": 10.0, "w": 29.0, "h": 12.0},
        {"key_id": "b", "gw": 20.0, "gh": 10.0, "w": 31.0, "h": 13.0},
        {"key_id": "solo", "gw": 30.0, "gh": 12.0, "w": 36.0, "h": 18.0},
        {"key_id": "c", "gw": 60.0, "gh": 30.0, "w": 57.0, "h": 30.0},
        {"key_id": "d", "gw": 60.0, "gh": 30.0, "w": 62.0, "h": 30.0},
    ]
    per_key_layout_tweaks = {"solo": {"dx": 1.0}, "c": {"sx": 9.0}, "d": {"sy": 9.0}}

    _sync_similar_sizes(items, per_key_layout_tweaks=per_key_layout_tweaks)

    assert per_key_layout_tweaks["a"]["sx"] == pytest.approx(1.5)
    assert per_key_layout_tweaks["a"]["sy"] == pytest.approx(1.25)
    assert per_key_layout_tweaks["b"]["sx"] == pytest.approx(1.5)
    assert per_key_layout_tweaks["b"]["sy"] == pytest.approx(1.25)
    assert per_key_layout_tweaks["solo"] == {"dx": 1.0}
    assert per_key_layout_tweaks["c"] == {"sx": 9.0}
    assert per_key_layout_tweaks["d"] == {"sy": 9.0}


def test_row_and_col_thresholds_use_median_global_dimensions() -> None:
    items = [
        {"gw": 10.0, "gh": 5.0},
        {"gw": 50.0, "gh": 20.0},
        {"gw": 80.0, "gh": 40.0},
    ]

    x_thresh, y_thresh = _row_and_col_thresholds(items)

    assert x_thresh == pytest.approx(4.0)
    assert y_thresh == pytest.approx(3.0)


def test_snap_rows_only_mutates_entries_with_meaningful_vertical_delta() -> None:
    items = [
        {"key_id": "a", "cy": 10.0},
        {"key_id": "b", "cy": 10.6},
        {"key_id": "c", "cy": 10.7},
        {"key_id": "solo", "cy": 20.0},
    ]
    per_key_layout_tweaks = {"a": {"dy": -0.2}, "c": {"dy": 2.0}, "solo": {"dy": 3.0}}

    _snap_rows(items2=items, y_thresh=1.0, per_key_layout_tweaks=per_key_layout_tweaks)

    assert per_key_layout_tweaks["a"]["dy"] == pytest.approx(0.4)
    assert "b" not in per_key_layout_tweaks
    assert per_key_layout_tweaks["c"]["dy"] == pytest.approx(2.0)
    assert per_key_layout_tweaks["solo"]["dy"] == pytest.approx(3.0)


def test_snap_cols_only_mutates_entries_with_meaningful_horizontal_delta() -> None:
    items = [
        {"key_id": "a", "cx": 5.0},
        {"key_id": "b", "cx": 5.6},
        {"key_id": "c", "cx": 5.7},
        {"key_id": "solo", "cx": 15.0},
    ]
    per_key_layout_tweaks = {"a": {"dx": 1.0}, "c": {"dx": 2.0}, "solo": {"dx": 3.0}}

    _snap_cols(items3=items, x_thresh=1.0, per_key_layout_tweaks=per_key_layout_tweaks)

    assert per_key_layout_tweaks["a"]["dx"] == pytest.approx(1.6)
    assert "b" not in per_key_layout_tweaks
    assert per_key_layout_tweaks["c"]["dx"] == pytest.approx(2.0)
    assert per_key_layout_tweaks["solo"]["dx"] == pytest.approx(3.0)


def test_auto_sync_per_key_overlays_is_noop_for_empty_key_sets() -> None:
    per_key_layout_tweaks = {"a": {"dx": 1.0, "dy": 2.0}}

    auto_sync_per_key_overlays(
        layout_tweaks={"dx": 5.0},
        per_key_layout_tweaks=per_key_layout_tweaks,
        keys=[],
        base_image_size=(100, 100),
    )

    assert per_key_layout_tweaks == {"a": {"dx": 1.0, "dy": 2.0}}


def test_auto_sync_per_key_overlays_normalizes_sizes_rows_and_columns_on_small_layout() -> None:
    keys = [
        _key("a", (10, 10, 30, 18)),
        _key("b", (50, 10, 30, 18)),
        _key("c", (10, 40, 30, 18)),
        _key("d", (50, 40, 30, 18)),
    ]
    per_key_layout_tweaks = {
        "b": {"sx": 31.0 / 30.0, "dy": 0.8},
        "c": {"sx": 29.0 / 30.0, "dx": 0.8},
        "d": {"sy": 17.0 / 18.0},
    }

    auto_sync_per_key_overlays(
        layout_tweaks={},
        per_key_layout_tweaks=per_key_layout_tweaks,
        keys=keys,
        base_image_size=(100, 100),
    )

    apply_global = _apply_global_factory(layout_tweaks={}, base_image_size=(100, 100))
    items = {
        item["key_id"]: item
        for item in _build_items(keys=keys, apply_global=apply_global, per_key_layout_tweaks=per_key_layout_tweaks)
    }

    for key_id in ("a", "b", "c", "d"):
        assert per_key_layout_tweaks[key_id]["sx"] == pytest.approx(1.0)
        assert per_key_layout_tweaks[key_id]["sy"] == pytest.approx(1.0)
        assert items[key_id]["w"] == pytest.approx(30.0)
        assert items[key_id]["h"] == pytest.approx(18.0)

    assert items["a"]["cy"] == pytest.approx(items["b"]["cy"])
    assert items["a"]["cx"] == pytest.approx(items["c"]["cx"])
    assert per_key_layout_tweaks["a"]["dy"] == pytest.approx(0.4)
    assert per_key_layout_tweaks["a"]["dx"] == pytest.approx(0.4)
    assert per_key_layout_tweaks["b"]["dy"] == pytest.approx(0.4)
    assert per_key_layout_tweaks["c"]["dx"] == pytest.approx(0.4)
    assert per_key_layout_tweaks["d"] == {"sx": pytest.approx(1.0), "sy": pytest.approx(1.0)}