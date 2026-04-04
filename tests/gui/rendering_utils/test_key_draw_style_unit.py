from __future__ import annotations

from src.gui.utils.key_draw_style import KeyDrawStyle, key_draw_style


def test_key_draw_style_for_unmapped_unselected_key() -> None:
    style = key_draw_style(mapped=False, selected=False)

    assert style == KeyDrawStyle(
        fill="",
        stipple="",
        text_fill="#cfcfcf",
        outline="#8a8a8a",
        width=2,
        dash=(3,),
    )


def test_key_draw_style_for_mapped_key_without_color() -> None:
    style = key_draw_style(mapped=True, selected=False, color=None)

    assert style == KeyDrawStyle(
        fill="#000000",
        stipple="gray75",
        text_fill="#e0e0e0",
        outline="#777777",
        width=2,
        dash=(),
    )


def test_key_draw_style_uses_black_text_for_bright_colors() -> None:
    style = key_draw_style(mapped=True, selected=False, color=(240, 240, 100))

    assert style.fill == "#f0f064"
    assert style.stipple == "gray50"
    assert style.text_fill == "#000000"
    assert style.outline == "#777777"
    assert style.width == 2
    assert style.dash == ()


def test_key_draw_style_uses_selected_outline_and_white_text_for_dark_colors() -> None:
    style = key_draw_style(mapped=True, selected=True, color=(10, 20, 30))

    assert style.fill == "#0a141e"
    assert style.stipple == "gray50"
    assert style.text_fill == "#ffffff"
    assert style.outline == "#00ffff"
    assert style.width == 3
    assert style.dash == ()
