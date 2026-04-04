from __future__ import annotations

from src.gui.utils.window_geometry import compute_centered_window_geometry


class _FakeRoot:
    def __init__(self, *, screen_w: int, screen_h: int) -> None:
        self._screen_w = int(screen_w)
        self._screen_h = int(screen_h)

    def winfo_screenwidth(self) -> int:
        return self._screen_w

    def winfo_screenheight(self) -> int:
        return self._screen_h


def test_compute_centered_window_geometry_uses_default_minimum_size_when_content_is_smaller() -> None:
    root = _FakeRoot(screen_w=2000, screen_h=1600)

    geometry = compute_centered_window_geometry(
        root,
        content_width_px=600,
        content_height_px=600,
        footer_height_px=100,
    )

    assert geometry == "1100x850+450+375"


def test_compute_centered_window_geometry_includes_content_footer_and_chrome_padding() -> None:
    root = _FakeRoot(screen_w=2200, screen_h=1800)

    geometry = compute_centered_window_geometry(
        root,
        content_width_px=1400,
        content_height_px=900,
        footer_height_px=120,
        chrome_padding_px=60,
    )

    assert geometry == "1400x1080+400+360"


def test_compute_centered_window_geometry_caps_window_size_to_screen_ratio() -> None:
    root = _FakeRoot(screen_w=1000, screen_h=900)

    geometry = compute_centered_window_geometry(
        root,
        content_width_px=1800,
        content_height_px=1000,
        footer_height_px=200,
        screen_ratio_cap=0.8,
    )

    assert geometry == "800x720+100+90"


def test_compute_centered_window_geometry_centers_using_floor_division_for_odd_remaining_space() -> None:
    root = _FakeRoot(screen_w=1367, screen_h=911)

    geometry = compute_centered_window_geometry(
        root,
        content_width_px=1101,
        content_height_px=701,
        footer_height_px=80,
        default_w=1000,
        default_h=800,
    )

    assert geometry == "1101x821+133+45"


def test_compute_centered_window_geometry_clamps_offsets_to_zero_when_window_exceeds_screen() -> None:
    root = _FakeRoot(screen_w=500, screen_h=400)

    geometry = compute_centered_window_geometry(
        root,
        content_width_px=900,
        content_height_px=700,
        footer_height_px=100,
        chrome_padding_px=50,
        screen_ratio_cap=2.0,
    )

    assert geometry == "1000x800+0+0"
