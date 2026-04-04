from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gui.reference.overlay_geometry import (
    CanvasTransform,
    apply_global_tweak,
    apply_per_key_tweak,
    calc_centered_drawn_bbox,
    calc_centered_transform,
    hit_test,
    inset_bbox,
    key_canvas_bbox_inset,
    key_canvas_hit_rects,
    key_canvas_rect,
    transform_from_drawn_bbox,
)


def _key(
    key_id: str,
    rect: tuple[float, float, float, float],
    *,
    shape_segments: tuple[tuple[float, float, float, float], ...] | None = None,
):
    return SimpleNamespace(
        key_id=key_id,
        rect=rect,
        shape_segments=shape_segments,
    )


def test_canvas_transform_maps_rect_to_canvas_coordinates() -> None:
    transform = CanvasTransform(x0=10.0, y0=20.0, sx=2.0, sy=3.0)

    assert transform.to_canvas((1.0, 2.0, 4.0, 5.0)) == (12.0, 26.0, 20.0, 41.0)


def test_centered_transform_and_drawn_bbox_preserve_aspect_ratio() -> None:
    transform = calc_centered_transform(canvas_w=200, canvas_h=100, image_size=(100, 50))
    bbox = calc_centered_drawn_bbox(canvas_w=200, canvas_h=100, image_size=(100, 50))

    assert transform == CanvasTransform(x0=0.0, y0=0.0, sx=2.0, sy=2.0)
    assert bbox == (0, 0, 200, 100, 2.0)


def test_transform_from_drawn_bbox_rebuilds_scale_and_origin() -> None:
    assert transform_from_drawn_bbox(x0=5, y0=7, draw_w=200, draw_h=100, image_size=(100, 50)) == CanvasTransform(
        x0=5.0,
        y0=7.0,
        sx=2.0,
        sy=2.0,
    )


def test_apply_global_and_per_key_tweaks_adjust_rect_geometry() -> None:
    global_rect = apply_global_tweak(
        rect=(40.0, 10.0, 20.0, 10.0),
        layout_tweaks={"dx": 3.0, "dy": -2.0, "sx": 1.5, "sy": 2.0},
        image_size=(100, 50),
    )

    assert global_rect == pytest.approx((38.0, -7.0, 30.0, 20.0))

    per_key_rect = apply_per_key_tweak(
        key_id="esc",
        rect=global_rect,
        per_key_layout_tweaks={"esc": {"dx": 2.0, "dy": 1.0, "sx": 0.5, "sy": 0.25, "inset": 0.1}},
        inset_default=0.06,
    )

    assert per_key_rect == pytest.approx((47.5, 1.5, 15.0, 5.0, 0.1))


def test_inset_bbox_handles_fraction_and_pixel_modes() -> None:
    assert inset_bbox(x1=0.0, y1=0.0, x2=20.0, y2=10.0, inset_value=0.1) == pytest.approx((1.0, 1.0, 19.0, 9.0))
    assert inset_bbox(x1=0.0, y1=0.0, x2=20.0, y2=10.0, inset_value=3.0) == pytest.approx((3.0, 3.0, 17.0, 7.0))


def test_key_canvas_rect_and_hit_rects_apply_transform_tweaks_and_segments() -> None:
    transform = CanvasTransform(x0=10.0, y0=20.0, sx=2.0, sy=2.0)
    key = _key(
        "enter",
        (10.0, 5.0, 20.0, 10.0),
        shape_segments=((0.0, 0.0, 0.5, 1.0), (0.5, 0.5, 0.5, 0.5)),
    )

    rect = key_canvas_rect(
        transform=transform,
        key=key,
        layout_tweaks={"dx": 2.0, "dy": 1.0, "sx": 1.0, "sy": 1.0, "inset": 0.1},
        per_key_layout_tweaks={"enter": {"dx": 1.0, "dy": 2.0, "sx": 1.5, "sy": 1.0, "inset": 0.05}},
        image_size=(100, 50),
    )

    assert rect == pytest.approx((26.0, 36.0, 86.0, 56.0, 0.05))

    hit_rects = key_canvas_hit_rects(
        transform=transform,
        key=key,
        layout_tweaks={"dx": 2.0, "dy": 1.0, "sx": 1.0, "sy": 1.0, "inset": 0.1},
        per_key_layout_tweaks={"enter": {"dx": 1.0, "dy": 2.0, "sx": 1.5, "sy": 1.0, "inset": 0.05}},
        image_size=(100, 50),
    )

    assert hit_rects[0] == pytest.approx((27.0, 37.0, 56.0, 55.0))
    assert hit_rects[1] == pytest.approx((56.0, 46.0, 85.0, 55.0))


def test_key_canvas_bbox_inset_can_cap_effective_inset() -> None:
    transform = CanvasTransform(x0=0.0, y0=0.0, sx=1.0, sy=1.0)
    key = _key("space", (0.0, 0.0, 20.0, 10.0))

    uncapped = key_canvas_bbox_inset(
        transform=transform,
        key=key,
        layout_tweaks={"inset": 0.4},
        per_key_layout_tweaks={},
        image_size=(100, 50),
    )
    capped = key_canvas_bbox_inset(
        transform=transform,
        key=key,
        layout_tweaks={"inset": 0.4},
        per_key_layout_tweaks={},
        image_size=(100, 50),
        inset_value_cap=0.1,
    )

    assert uncapped == pytest.approx((4.0, 4.0, 16.0, 6.0))
    assert capped == pytest.approx((1.0, 1.0, 19.0, 9.0))


def test_hit_test_returns_first_matching_key_and_none_when_missed() -> None:
    transform = CanvasTransform(x0=0.0, y0=0.0, sx=1.0, sy=1.0)
    keys = (
        _key("a", (0.0, 0.0, 10.0, 10.0)),
        _key("b", (20.0, 0.0, 10.0, 10.0)),
    )

    assert (
        hit_test(
            transform=transform,
            x=5,
            y=5,
            layout_tweaks={},
            per_key_layout_tweaks={},
            keys=keys,
            image_size=(100, 50),
        )
        is keys[0]
    )
    assert (
        hit_test(
            transform=transform,
            x=99,
            y=99,
            layout_tweaks={},
            per_key_layout_tweaks={},
            keys=keys,
            image_size=(100, 50),
        )
        is None
    )
