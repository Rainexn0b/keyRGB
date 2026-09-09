from __future__ import annotations

import pytest

from keyrgb.gui.theme import ttk as ttk_theme
from keyrgb.gui.theme.contrast import contrast_ratio


@pytest.mark.parametrize(
    ("fg", "bg", "label"),
    [
        (ttk_theme.DARK_FG, ttk_theme.DARK_BG, "dark text on window bg"),
        (ttk_theme.DARK_FG, ttk_theme.DARK_FIELD_BG, "dark text on field"),
        (ttk_theme.DARK_FG, ttk_theme.DARK_BUTTON_BG, "dark text on button"),
        (ttk_theme.DARK_ACTION_FG, ttk_theme.DARK_PRIMARY_BG, "dark primary action"),
        (ttk_theme.DARK_ACTION_FG, ttk_theme.DARK_DESTRUCTIVE_BG, "dark destructive action"),
        ("#000000", "#f0f0f0", "light fallback text on window bg"),
        ("#000000", "#ffffff", "light fallback text on field"),
        ("#111111", "#fafafa", "light lookup text on window bg"),
        ("#111111", "#ffffff", "light lookup text on field"),
        (ttk_theme.LIGHT_ACTION_FG, ttk_theme.LIGHT_PRIMARY_BG, "light primary action"),
        (ttk_theme.LIGHT_ACTION_FG, ttk_theme.LIGHT_DESTRUCTIVE_BG, "light destructive action"),
    ],
)
def test_normal_text_meets_45_to_1(fg: str, bg: str, label: str) -> None:
    assert contrast_ratio(fg, bg) >= ttk_theme.NORMAL_CONTRAST_TARGET, label


@pytest.mark.parametrize(
    ("fg", "bg", "label"),
    [
        (ttk_theme.DARK_DISABLED_FG, ttk_theme.DARK_BG, "dark disabled on window bg"),
        (ttk_theme.DARK_DISABLED_FG, ttk_theme.DARK_FIELD_BG, "dark disabled on field"),
        (ttk_theme.DARK_DISABLED_FG, ttk_theme.DARK_BUTTON_BG, "dark disabled on button"),
        (ttk_theme.LIGHT_DISABLED_FG, "#f0f0f0", "light disabled on fallback bg"),
        (ttk_theme.LIGHT_DISABLED_FG, "#ffffff", "light disabled on field"),
        (ttk_theme.LIGHT_DISABLED_FG, "#fafafa", "light disabled on lookup bg"),
    ],
)
def test_disabled_text_meets_usability_floor_of_3_to_1(fg: str, bg: str, label: str) -> None:
    assert contrast_ratio(fg, bg) >= ttk_theme.DISABLED_CONTRAST_TARGET, label
