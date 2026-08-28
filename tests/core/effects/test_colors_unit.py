from __future__ import annotations

import pytest

from keyrgb.core.effects import colors


def _cases():
    yield ((100, 50, 25), 0, (0, 0, 0))
    yield ((100, 50, 25), -5, (0, 0, 0))
    yield ((100, 50, 25), 50, (100, 50, 25))
    yield ((100, 50, 25), 25, (50, 25, 12))  # round(int(c) * 25/50); round(12.5)=12
    yield ((255, 255, 255), 50, (255, 255, 255))
    yield ((300, -10, 128), 50, (255, 0, 128))  # channel clamp on full brightness
    yield ((300, -10, 128), 25, (150, 0, 64))  # scale before clamp
    yield ((10.7, 20.3, 30.9), 50, (10, 20, 30))  # float channel int-convert
    yield ((10.7, 20.3, 30.9), 25, (5, 10, 15))  # float channel scale+round
    yield ((100, 50, 25), 99, (100, 50, 25))  # brightness > max clamps to full
    yield ((100, 50, 25), 1, (round(100 / 50), round(50 / 50), round(25 / 50)))


@pytest.mark.parametrize("color,brightness,expected", list(_cases()))
def test_scale_color_for_brightness_edge_cases(color, brightness, expected) -> None:
    assert colors.scale_color_for_brightness(color, brightness) == expected


def test_scale_color_for_brightness_output_shape_and_types() -> None:
    result = colors.scale_color_for_brightness((100, 50, 25), 25)

    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(isinstance(channel, int) for channel in result)


def test_scale_color_for_brightness_uses_shared_ui_range() -> None:
    # Brightness exactly at the shared UI maximum yields un-scaled (clamped) channels.
    assert colors.scale_color_for_brightness((200, 100, 50), colors.UI_BRIGHTNESS_MAX) == (200, 100, 50)
