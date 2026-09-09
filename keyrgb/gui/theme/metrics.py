"""Semantic ttk style names, named-font roles, and spacing metrics.

Downstream windows should use these style names instead of local
``("Sans", N, ...)`` tuples so typography and padding stay consistent.
Actual ``ttk.Style`` configuration lives in :mod:`keyrgb.gui.theme.ttk`;
this module only owns the stable names and numeric gaps.
"""

from __future__ import annotations

from typing import Literal

FontWeight = Literal["normal", "bold"]

# Semantic label styles.
TITLE_LABEL_STYLE = "KeyRGB.Title.TLabel"
SECTION_LABEL_STYLE = "KeyRGB.Section.TLabel"
BODY_LABEL_STYLE = "KeyRGB.Body.TLabel"
CAPTION_LABEL_STYLE = "KeyRGB.Caption.TLabel"
STATUS_LABEL_STYLE = "KeyRGB.Status.TLabel"
VALUE_LABEL_STYLE = "KeyRGB.Value.TLabel"

# Semantic action styles.
PRIMARY_BUTTON_STYLE = "KeyRGB.Primary.TButton"
DESTRUCTIVE_BUTTON_STYLE = "KeyRGB.Destructive.TButton"

SEMANTIC_LABEL_STYLES: tuple[str, ...] = (
    TITLE_LABEL_STYLE,
    SECTION_LABEL_STYLE,
    BODY_LABEL_STYLE,
    CAPTION_LABEL_STYLE,
    STATUS_LABEL_STYLE,
    VALUE_LABEL_STYLE,
)

SEMANTIC_BUTTON_STYLES: tuple[str, ...] = (
    PRIMARY_BUTTON_STYLE,
    DESTRUCTIVE_BUTTON_STYLE,
)

ALL_SEMANTIC_STYLES: tuple[str, ...] = SEMANTIC_LABEL_STYLES + SEMANTIC_BUTTON_STYLES

# Base ttk styles that always receive visible keyboard-focus mapping.
FOCUSABLE_BASE_STYLES: tuple[str, ...] = (
    "TButton",
    "TCheckbutton",
    "TRadiobutton",
    "TEntry",
    "TCombobox",
    "TSpinbox",
    "TScale",
    "TScrollbar",
)

# Tk named-font roles backing the semantic styles. Roles use absolute point
# sizes on the system-resolved "Sans" alias so named fonts preserve the
# established visual hierarchy (Sans 14/11/10/9/8); Tk scaling (including
# KEYRGB_TK_SCALING) still applies on top because sizes stay in points.
THEME_FONT_FAMILY = "Sans"
TITLE_FONT_NAME = "KeyRGB.Title"
SECTION_FONT_NAME = "KeyRGB.Section"
BODY_FONT_NAME = "KeyRGB.Body"
CAPTION_FONT_NAME = "KeyRGB.Caption"
STATUS_FONT_NAME = "KeyRGB.Status"
VALUE_FONT_NAME = "KeyRGB.Value"
ACTION_FONT_NAME = "KeyRGB.Action"

FONT_NAME_BY_STYLE: dict[str, str] = {
    TITLE_LABEL_STYLE: TITLE_FONT_NAME,
    SECTION_LABEL_STYLE: SECTION_FONT_NAME,
    BODY_LABEL_STYLE: BODY_FONT_NAME,
    CAPTION_LABEL_STYLE: CAPTION_FONT_NAME,
    STATUS_LABEL_STYLE: STATUS_FONT_NAME,
    VALUE_LABEL_STYLE: VALUE_FONT_NAME,
    PRIMARY_BUTTON_STYLE: ACTION_FONT_NAME,
    DESTRUCTIVE_BUTTON_STYLE: ACTION_FONT_NAME,
}

# (absolute point size, weight) per named font. Sizes match the established
# window semantics: title 14, section 11, value 10, body/status/action 9,
# caption 8. Absolute sizes (not TkDefaultFont deltas) avoid inheriting
# unexpected base families/sizes such as fixed 8.
FONT_SPECS: dict[str, tuple[int, FontWeight]] = {
    TITLE_FONT_NAME: (14, "bold"),
    SECTION_FONT_NAME: (11, "bold"),
    BODY_FONT_NAME: (9, "normal"),
    CAPTION_FONT_NAME: (8, "normal"),
    STATUS_FONT_NAME: (9, "normal"),
    VALUE_FONT_NAME: (10, "bold"),
    ACTION_FONT_NAME: (9, "bold"),
}

# Spacing metrics (pixels at scale 1.0; Tk scaling applies on top).
OUTER_PAD_X = 12
OUTER_PAD_Y = 12
SECTION_GAP_Y = 12
CONTROL_GAP_Y = 6
INLINE_GAP_X = 4
COMPACT_GAP = 4

OUTER_PADDING: tuple[int, int] = (OUTER_PAD_X, OUTER_PAD_Y)

__all__ = [
    "ACTION_FONT_NAME",
    "ALL_SEMANTIC_STYLES",
    "BODY_FONT_NAME",
    "BODY_LABEL_STYLE",
    "CAPTION_FONT_NAME",
    "CAPTION_LABEL_STYLE",
    "COMPACT_GAP",
    "CONTROL_GAP_Y",
    "DESTRUCTIVE_BUTTON_STYLE",
    "FOCUSABLE_BASE_STYLES",
    "FONT_NAME_BY_STYLE",
    "FONT_SPECS",
    "INLINE_GAP_X",
    "OUTER_PADDING",
    "OUTER_PAD_X",
    "OUTER_PAD_Y",
    "PRIMARY_BUTTON_STYLE",
    "SECTION_FONT_NAME",
    "SECTION_GAP_Y",
    "SECTION_LABEL_STYLE",
    "SEMANTIC_BUTTON_STYLES",
    "SEMANTIC_LABEL_STYLES",
    "STATUS_FONT_NAME",
    "STATUS_LABEL_STYLE",
    "THEME_FONT_FAMILY",
    "TITLE_FONT_NAME",
    "TITLE_LABEL_STYLE",
    "VALUE_FONT_NAME",
    "VALUE_LABEL_STYLE",
    "FontWeight",
]
