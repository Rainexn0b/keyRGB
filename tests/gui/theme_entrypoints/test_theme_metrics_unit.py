from __future__ import annotations

from keyrgb.gui.theme import metrics


def test_semantic_style_names_cover_required_roles() -> None:
    assert metrics.TITLE_LABEL_STYLE == "KeyRGB.Title.TLabel"
    assert metrics.SECTION_LABEL_STYLE == "KeyRGB.Section.TLabel"
    assert metrics.BODY_LABEL_STYLE == "KeyRGB.Body.TLabel"
    assert metrics.CAPTION_LABEL_STYLE == "KeyRGB.Caption.TLabel"
    assert metrics.STATUS_LABEL_STYLE == "KeyRGB.Status.TLabel"
    assert metrics.VALUE_LABEL_STYLE == "KeyRGB.Value.TLabel"
    assert metrics.PRIMARY_BUTTON_STYLE == "KeyRGB.Primary.TButton"
    assert metrics.DESTRUCTIVE_BUTTON_STYLE == "KeyRGB.Destructive.TButton"
    for role in metrics.ALL_SEMANTIC_STYLES:
        assert role in metrics.FONT_NAME_BY_STYLE
        assert metrics.FONT_NAME_BY_STYLE[role] in metrics.FONT_SPECS


def test_spacing_metrics_cover_outer_section_and_control_gaps() -> None:
    assert metrics.OUTER_PAD_X == 12
    assert metrics.OUTER_PAD_Y == 12
    assert metrics.SECTION_GAP_Y == 12
    assert metrics.CONTROL_GAP_Y == 6
    assert metrics.INLINE_GAP_X == 4
    assert metrics.OUTER_PADDING == (metrics.OUTER_PAD_X, metrics.OUTER_PAD_Y)
    # Gaps must order outer >= section >= control for a calm hierarchy.
    assert metrics.OUTER_PAD_Y >= metrics.SECTION_GAP_Y >= metrics.CONTROL_GAP_Y


def test_font_roles_preserve_established_absolute_sizes() -> None:
    assert metrics.THEME_FONT_FAMILY == "Sans"
    assert metrics.FONT_SPECS == {
        metrics.TITLE_FONT_NAME: (14, "bold"),
        metrics.SECTION_FONT_NAME: (11, "bold"),
        metrics.BODY_FONT_NAME: (9, "normal"),
        metrics.CAPTION_FONT_NAME: (8, "normal"),
        metrics.STATUS_FONT_NAME: (9, "normal"),
        metrics.VALUE_FONT_NAME: (10, "bold"),
        metrics.ACTION_FONT_NAME: (9, "bold"),
    }


def test_focusable_styles_cover_interactive_controls() -> None:
    for expected in (
        "TButton",
        "TCheckbutton",
        "TRadiobutton",
        "TEntry",
        "TCombobox",
        "TSpinbox",
        "TScale",
        "TScrollbar",
    ):
        assert expected in metrics.FOCUSABLE_BASE_STYLES
