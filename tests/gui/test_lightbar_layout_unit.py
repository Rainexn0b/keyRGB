from __future__ import annotations

import pytest

from src.core.resources.defaults import get_default_lightbar_overlay
from src.gui.perkey.lightbar_layout import lightbar_rect_for_size, normalize_lightbar_overlay


def test_normalize_lightbar_overlay_clamps_supported_ranges() -> None:
    payload = normalize_lightbar_overlay(
        {
            "visible": 0,
            "length": 3.0,
            "thickness": -1.0,
            "dx": 4.0,
            "dy": -4.0,
            "inset": 1.0,
        }
    )

    assert payload == {
        "visible": False,
        "length": pytest.approx(1.0),
        "thickness": pytest.approx(0.04),
        "dx": pytest.approx(0.5),
        "dy": pytest.approx(-0.5),
        "inset": pytest.approx(0.25),
    }


def test_lightbar_rect_for_size_returns_none_when_hidden() -> None:
    payload = dict(get_default_lightbar_overlay())
    payload["visible"] = False

    assert lightbar_rect_for_size(width=320.0, height=180.0, overlay=payload) is None


def test_lightbar_rect_for_size_stays_within_canvas_bounds() -> None:
    rect = lightbar_rect_for_size(
        width=320.0,
        height=180.0,
        overlay={"visible": True, "length": 0.8, "thickness": 0.2, "dx": 0.1, "dy": -0.1, "inset": 0.05},
    )

    assert rect is not None
    x1, y1, x2, y2 = rect
    assert 0.0 <= x1 < x2 <= 320.0
    assert 0.0 <= y1 < y2 <= 180.0