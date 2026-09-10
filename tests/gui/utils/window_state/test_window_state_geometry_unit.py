from __future__ import annotations

"""Window-state geometry preparation and formatting."""

import pytest

from keyrgb.gui.utils.window_state import (
    WindowGeometry,
    geometry_string,
    prepare_restored_geometry,
)


# --- prepare / clamp / offscreen / formatting --------------------------------
def test_prepare_clamps_to_min_and_screen_cap() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=100, height=100), 1920, 1080, 460, 520, 0.95)
    assert prepared == WindowGeometry(width=460, height=520, x=(1920 - 460) // 2, y=(1080 - 520) // 2)
    prepared = prepare_restored_geometry(WindowGeometry(width=5000, height=5000), 1920, 1080, 460, 520, 0.95)
    assert prepared == WindowGeometry(
        width=int(1920 * 0.95),
        height=int(1080 * 0.95),
        x=(1920 - int(1920 * 0.95)) // 2,
        y=(1080 - int(1080 * 0.95)) // 2,
    )


def test_prepare_tiny_screen_keeps_window_within_screen_cap() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=800, height=600), 400, 300, 460, 520, 0.95)
    assert prepared == WindowGeometry(width=380, height=285, x=10, y=7)


def test_prepare_size_only_returns_centered() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=800, height=600), 1920, 1080, 460, 520, 0.95)
    assert prepared is not None
    assert prepared.width == 800 and prepared.height == 600
    assert (prepared.x, prepared.y) == ((1920 - 800) // 2, (1080 - 600) // 2)
    assert geometry_string(prepared) == f"{prepared.width}x{prepared.height}{prepared.x:+d}{prepared.y:+d}"
    assert geometry_string(prepared) == "800x600+560+240"


def test_prepare_size_only_centers_clamped_dimensions_on_smaller_screen() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=800, height=600), 400, 300, 460, 520, 0.95)
    assert prepared is not None
    assert (prepared.width, prepared.height) == (380, 285)
    assert (prepared.x, prepared.y) == ((400 - 380) // 2, (300 - 285) // 2)
    assert geometry_string(prepared) == "380x285+10+7"


@pytest.mark.parametrize(
    "geometry",
    [
        WindowGeometry(width=800, height=600, x=5000, y=5000),
        WindowGeometry(width=800, height=600, x=-900, y=-700),
        WindowGeometry(width=800, height=600, x=1920, y=100),
        WindowGeometry(width=800, height=600, x=100, y=1080),
    ],
)
def test_prepare_wholly_offscreen_rejected(geometry) -> None:
    assert prepare_restored_geometry(geometry, 1920, 1080, 460, 520, 0.95) is None


def test_prepare_partially_visible_kept() -> None:
    prepared = prepare_restored_geometry(
        WindowGeometry(width=800, height=600, x=-100, y=-100), 1920, 1080, 460, 520, 0.95
    )
    assert prepared == WindowGeometry(width=800, height=600, x=-100, y=-100)


def test_prepare_malformed_inputs_rejected() -> None:
    assert prepare_restored_geometry(None, 1920, 1080, 460, 520, 0.95) is None  # type: ignore[arg-type]
    assert prepare_restored_geometry(WindowGeometry(width=0, height=600), 1920, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=10**9, height=600), 1920, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=800, height=600), 0, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=800, height=600), 1920, 1080, 0, 520, 0.95) is None


def test_geometry_string_formats() -> None:
    assert geometry_string(WindowGeometry(width=800, height=600)) == "800x600"
    assert geometry_string(WindowGeometry(width=800, height=600, x=10, y=20)) == "800x600+10+20"
    assert geometry_string(WindowGeometry(width=800, height=600, x=-10, y=-20)) == "800x600-10-20"
