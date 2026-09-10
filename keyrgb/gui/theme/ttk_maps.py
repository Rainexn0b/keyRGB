"""Style-map builders for the KeyRGB ttk themes.

Owns the disabled-state/focus ``style.map`` tables and the semantic
label/action styles so ``ttk.py`` stays small. Both theme entry points
(``apply_clam_light_theme``/``apply_clam_dark_theme``) resolve through here.
"""

from __future__ import annotations

from tkinter import ttk

from . import metrics


def apply_state_maps(
    style: ttk.Style,
    *,
    bg: str,
    fg: str,
    field_bg: str,
    disabled_fg: str,
    focus_color: str,
    button_active_bg: str,
    button_disabled_bg: str,
) -> None:
    """Centralize disabled-state and keyboard-focus maps for base widgets."""

    style.map(
        "TButton",
        background=[
            ("disabled", button_disabled_bg),
            ("active", button_active_bg),
            ("focus", button_active_bg),
        ],
        foreground=[("disabled", disabled_fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TCheckbutton",
        background=[("disabled", bg), ("active", bg), ("focus", bg)],
        foreground=[("disabled", disabled_fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TRadiobutton",
        background=[("disabled", bg), ("active", bg), ("focus", bg)],
        foreground=[("disabled", disabled_fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", field_bg), ("focus", field_bg)],
        foreground=[("disabled", disabled_fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("disabled", field_bg), ("readonly", field_bg), ("focus", field_bg)],
        foreground=[("disabled", disabled_fg), ("readonly", fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TSpinbox",
        fieldbackground=[("disabled", field_bg), ("focus", field_bg)],
        foreground=[("disabled", disabled_fg), ("!disabled", fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TScale",
        background=[("disabled", bg), ("focus", bg)],
        troughcolor=[("disabled", field_bg), ("focus", field_bg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        "TScrollbar",
        background=[("disabled", bg), ("focus", bg)],
        troughcolor=[("disabled", field_bg), ("focus", field_bg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )


def apply_semantic_styles(
    style: ttk.Style,
    *,
    bg: str,
    fg: str,
    disabled_fg: str,
    focus_color: str,
    primary_bg: str,
    primary_active_bg: str,
    destructive_bg: str,
    destructive_active_bg: str,
    action_fg: str,
    fonts: dict[str, str],
) -> None:
    """Configure semantic label/action styles sharing the palette."""

    label_roles = (
        metrics.TITLE_LABEL_STYLE,
        metrics.SECTION_LABEL_STYLE,
        metrics.BODY_LABEL_STYLE,
        metrics.CAPTION_LABEL_STYLE,
        metrics.STATUS_LABEL_STYLE,
        metrics.VALUE_LABEL_STYLE,
    )
    for role in label_roles:
        options: dict[str, object] = {"background": bg, "foreground": fg}
        font_name = fonts.get(role)
        if font_name:
            options["font"] = font_name
        style.configure(role, **options)

    primary_options: dict[str, object] = {"background": primary_bg, "foreground": action_fg}
    destructive_options: dict[str, object] = {"background": destructive_bg, "foreground": action_fg}
    primary_font = fonts.get(metrics.PRIMARY_BUTTON_STYLE)
    destructive_font = fonts.get(metrics.DESTRUCTIVE_BUTTON_STYLE)
    if primary_font:
        primary_options["font"] = primary_font
    if destructive_font:
        destructive_options["font"] = destructive_font
    style.configure(metrics.PRIMARY_BUTTON_STYLE, **primary_options)
    style.configure(metrics.DESTRUCTIVE_BUTTON_STYLE, **destructive_options)

    style.map(
        metrics.PRIMARY_BUTTON_STYLE,
        background=[
            ("disabled", bg),
            ("active", primary_active_bg),
            ("focus", primary_active_bg),
        ],
        foreground=[("disabled", disabled_fg), ("!disabled", action_fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
    style.map(
        metrics.DESTRUCTIVE_BUTTON_STYLE,
        background=[
            ("disabled", bg),
            ("active", destructive_active_bg),
            ("focus", destructive_active_bg),
        ],
        foreground=[("disabled", disabled_fg), ("!disabled", action_fg)],
        bordercolor=[("focus", focus_color)],
        focuscolor=[("focus", focus_color)],
    )
