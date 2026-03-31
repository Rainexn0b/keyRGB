from __future__ import annotations

import pytest

from src.gui.widgets.color_wheel.utils import (
    derive_border_hex,
    hex_to_rgb,
    hsv_to_xy,
    invoke_callback,
    rgb_to_hex,
    xy_to_hsv,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#123abc", (0x12, 0x3A, 0xBC)),
        ("abc", (0xAA, 0xBB, 0xCC)),
        ("  #F0a  ", (0xFF, 0x00, 0xAA)),
    ],
)
def test_hex_to_rgb_accepts_full_and_shorthand_hex(value: str, expected: tuple[int, int, int]) -> None:
    assert hex_to_rgb(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", None, "#12", "xyzxyz", "#12gg34"],
)
def test_hex_to_rgb_returns_default_for_invalid_values(value: str | None) -> None:
    assert hex_to_rgb(value) == (0x2B, 0x2B, 0x2B)


def test_rgb_to_hex_formats_and_masks_channel_values() -> None:
    assert rgb_to_hex((0x12, 0x34, 0x56)) == "#123456"
    assert rgb_to_hex((-1, 256, 0x123)) == "#ff0023"


def test_derive_border_hex_darkens_light_backgrounds_and_lightens_dark_backgrounds() -> None:
    assert derive_border_hex((255, 255, 255)) == "#bfbfbf"
    assert derive_border_hex((0, 0, 0)) == "#595959"


def test_invoke_callback_passes_through_kwargs_for_modern_callbacks() -> None:
    calls: list[tuple[tuple[int, int, int], dict[str, object]]] = []

    def callback(*args: int, **kwargs: object) -> None:
        calls.append((args, kwargs))

    invoke_callback(callback, 1, 2, 3, source="wheel")

    assert calls == [((1, 2, 3), {"source": "wheel"})]


def test_invoke_callback_retries_without_kwargs_on_type_error() -> None:
    calls: list[tuple[int, int, int]] = []

    def legacy_callback(r: int, g: int, b: int) -> None:
        calls.append((r, g, b))

    invoke_callback(legacy_callback, 4, 5, 6, source="wheel")

    assert calls == [(4, 5, 6)]


def test_xy_to_hsv_returns_none_outside_wheel_and_center_circle_at_origin() -> None:
    radius = 100.0

    assert xy_to_hsv(int(radius * 2) + 1, int(radius), radius) is None
    assert xy_to_hsv(int(radius), int(radius), radius) == (None, 0.0)


@pytest.mark.parametrize("hue", [0.0, 0.125, 0.5, 0.875])
@pytest.mark.parametrize("saturation", [0.35, 0.75, 1.0])
def test_hsv_and_xy_conversion_round_trip_is_reasonably_close(hue: float, saturation: float) -> None:
    radius = 100.0

    x, y = hsv_to_xy(hue, saturation, radius)
    result = xy_to_hsv(int(round(x)), int(round(y)), radius)

    assert result is not None
    round_trip_hue, round_trip_saturation = result
    assert round_trip_hue is not None
    assert round_trip_hue == pytest.approx(hue, abs=0.02)
    assert round_trip_saturation == pytest.approx(saturation, abs=0.02)


def test_hsv_to_xy_places_zero_saturation_at_wheel_center() -> None:
    radius = 80.0

    assert hsv_to_xy(0.33, 0.0, radius) == pytest.approx((radius, radius))