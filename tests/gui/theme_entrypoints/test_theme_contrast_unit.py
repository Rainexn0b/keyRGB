from __future__ import annotations

import pytest

from keyrgb.gui.theme.contrast import (
    contrast_ratio,
    meets_contrast,
    parse_hex_color,
    relative_luminance,
)


def test_parse_hex_color_accepts_strict_lowercase_and_uppercase() -> None:
    assert parse_hex_color("#000000") == (0, 0, 0)
    assert parse_hex_color("#ffffff") == (255, 255, 255)
    assert parse_hex_color("#2B2B2B") == (43, 43, 43)


@pytest.mark.parametrize(
    "value",
    ["#fff", "#fffffff", "#ffffff00", "ffffff", "#gggggg", "#12345", "", "  #ffffff", "#ffffff "],
)
def test_parse_hex_color_rejects_non_strict_forms(value: str) -> None:
    with pytest.raises(ValueError):
        parse_hex_color(value)


def test_parse_hex_color_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        parse_hex_color(123)  # type: ignore[arg-type]


def test_relative_luminance_endpoints() -> None:
    assert relative_luminance("#000000") == pytest.approx(0.0)
    assert relative_luminance("#ffffff") == pytest.approx(1.0)


def test_contrast_ratio_black_on_white_is_21_to_1() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)


def test_contrast_ratio_same_color_is_1_to_1() -> None:
    assert contrast_ratio("#3a3a3a", "#3a3a3a") == pytest.approx(1.0)


def test_contrast_ratio_rejects_invalid_hex() -> None:
    with pytest.raises(ValueError):
        contrast_ratio("#fff", "#ffffff")


def test_meets_contrast_threshold() -> None:
    assert meets_contrast("#000000", "#ffffff", 4.5)
    assert not meets_contrast("#777777", "#3a3a3a", 3.0)
