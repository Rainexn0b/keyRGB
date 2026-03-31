from __future__ import annotations

import pytest

from src.gui.perkey.canvas_impl.canvas_hit_testing import (
    cursor_for_edges,
    point_in_bbox,
    point_near_bbox,
    resize_edges_for_point_in_bbox,
)


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        pytest.param((10.0, 25.0), "l", id="left"),
        pytest.param((30.0, 25.0), "r", id="right"),
        pytest.param((20.0, 20.0), "t", id="top"),
        pytest.param((20.0, 40.0), "b", id="bottom"),
        pytest.param((10.0, 20.0), "lt", id="top-left-corner"),
        pytest.param((30.0, 20.0), "rt", id="top-right-corner"),
        pytest.param((10.0, 40.0), "lb", id="bottom-left-corner"),
        pytest.param((30.0, 40.0), "rb", id="bottom-right-corner"),
    ],
)
def test_resize_edges_for_point_in_bbox_detects_edges_and_corners(
    point: tuple[float, float], expected: str
) -> None:
    cx, cy = point

    assert (
        resize_edges_for_point_in_bbox(
            x1=10.0,
            y1=20.0,
            x2=30.0,
            y2=40.0,
            cx=cx,
            cy=cy,
            thresh=2.0,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        pytest.param((8.0, 25.0), "l", id="left-threshold-inclusive"),
        pytest.param((32.0, 25.0), "r", id="right-threshold-inclusive"),
        pytest.param((20.0, 18.0), "t", id="top-threshold-inclusive"),
        pytest.param((20.0, 42.0), "b", id="bottom-threshold-inclusive"),
        pytest.param((7.9, 25.0), "", id="left-outside-threshold"),
        pytest.param((32.1, 25.0), "", id="right-outside-threshold"),
        pytest.param((20.0, 17.9), "", id="top-outside-threshold"),
        pytest.param((20.0, 42.1), "", id="bottom-outside-threshold"),
    ],
)
def test_resize_edges_for_point_in_bbox_honors_threshold_boundaries(
    point: tuple[float, float], expected: str
) -> None:
    cx, cy = point

    assert (
        resize_edges_for_point_in_bbox(
            x1=10.0,
            y1=20.0,
            x2=30.0,
            y2=40.0,
            cx=cx,
            cy=cy,
            thresh=2.0,
        )
        == expected
    )


def test_resize_edges_for_point_in_bbox_excludes_points_outside_axis_ranges() -> None:
    assert (
        resize_edges_for_point_in_bbox(
            x1=10.0,
            y1=20.0,
            x2=30.0,
            y2=40.0,
            cx=10.0,
            cy=42.1,
            thresh=2.0,
        )
        == ""
    )
    assert (
        resize_edges_for_point_in_bbox(
            x1=10.0,
            y1=20.0,
            x2=30.0,
            y2=40.0,
            cx=32.1,
            cy=20.0,
            thresh=2.0,
        )
        == ""
    )


@pytest.mark.parametrize(
    ("edges", "expected"),
    [
        pytest.param("lt", "top_left_corner", id="left-top-diagonal"),
        pytest.param("rb", "top_left_corner", id="right-bottom-diagonal"),
        pytest.param("rt", "top_right_corner", id="right-top-diagonal"),
        pytest.param("lb", "top_right_corner", id="left-bottom-diagonal"),
        pytest.param("l", "sb_h_double_arrow", id="horizontal-left"),
        pytest.param("r", "sb_h_double_arrow", id="horizontal-right"),
        pytest.param("t", "sb_v_double_arrow", id="vertical-top"),
        pytest.param("b", "sb_v_double_arrow", id="vertical-bottom"),
        pytest.param("", "", id="empty"),
    ],
)
def test_cursor_for_edges_maps_edge_sets_to_expected_cursor(edges: str, expected: str) -> None:
    assert cursor_for_edges(edges) == expected


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        pytest.param((10.0, 20.0), True, id="top-left-boundary"),
        pytest.param((30.0, 40.0), True, id="bottom-right-boundary"),
        pytest.param((20.0, 30.0), True, id="interior"),
        pytest.param((9.9, 20.0), False, id="left-outside"),
        pytest.param((30.1, 40.0), False, id="right-outside"),
        pytest.param((20.0, 40.1), False, id="bottom-outside"),
    ],
)
def test_point_in_bbox_includes_boundaries(point: tuple[float, float], expected: bool) -> None:
    cx, cy = point

    assert point_in_bbox(x1=10.0, y1=20.0, x2=30.0, y2=40.0, cx=cx, cy=cy) is expected


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        pytest.param((8.0, 18.0), True, id="padded-corner-inclusive"),
        pytest.param((32.0, 42.0), True, id="padded-opposite-corner-inclusive"),
        pytest.param((7.9, 18.0), False, id="outside-left-padding"),
        pytest.param((32.0, 42.1), False, id="outside-bottom-padding"),
    ],
)
def test_point_near_bbox_uses_padding_for_inclusion(point: tuple[float, float], expected: bool) -> None:
    cx, cy = point

    assert point_near_bbox(x1=10.0, y1=20.0, x2=30.0, y2=40.0, cx=cx, cy=cy, pad=2.0) is expected