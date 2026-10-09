"""Style-map builders for the KeyRGB ttk themes.

Owns the disabled-state/focus ``style.map`` tables and the semantic
label/action styles so ``ttk.py`` stays small. Both theme entry points
(``apply_clam_light_theme``/``apply_clam_dark_theme``) resolve through here.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import metrics


def apply_classic_palette(root: tk.Misc, bg: str, fg: str, border: str, selection: str) -> None:
    """Theme implicit preview canvases and ttk's classic combobox popup.

    Explicit widget options (keyboard artwork and color-wheel markers) win.
    Widget-default priority also preserves user option-database overrides.
    """

    for pattern, color in (
        ("*Canvas.background", bg),
        ("*Canvas.highlightBackground", border),
        ("*Canvas.highlightColor", selection),
        ("*TCombobox*Listbox.background", bg),
        ("*TCombobox*Listbox.foreground", fg),
        ("*TCombobox*Listbox.selectBackground", selection),
        ("*TCombobox*Listbox.selectForeground", "#ffffff"),
    ):
        root.option_add(pattern, color, "widgetDefault")


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

    # A neutral, flat rule separates editor tabs from their content in either
    # palette; it deliberately does not add a border around the panel.
    style.configure(metrics.TAB_DIVIDER_FRAME_STYLE, background="#707070", borderwidth=0)

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


def apply_dark_surfaces(
    style: ttk.Style,
    *,
    bg: str,
    fg: str,
    field_bg: str,
    border: str,
    disabled_fg: str,
    focus: str,
    button_bg: str,
    hover_bg: str,
    primary_bg: str,
    primary_active_bg: str,
    destructive_bg: str,
    destructive_active_bg: str,
) -> None:
    """Flat surfaces retaining native control layouts and interaction bindings."""

    # Clam's light/dark colors are separate from background and bordercolor.
    # Its pressed/selected maps otherwise reintroduce the stock white bevels.
    style.configure(".", background=bg, foreground=fg, bordercolor=border, lightcolor=bg, darkcolor=bg)
    style.map(".", background=[("disabled", bg), ("active", bg)])

    for name, surface, active in (
        ("TButton", button_bg, hover_bg),
        (metrics.PRIMARY_BUTTON_STYLE, primary_bg, primary_active_bg),
        (metrics.DESTRUCTIVE_BUTTON_STYLE, destructive_bg, destructive_active_bg),
    ):
        style.configure(name, relief="flat", borderwidth=1, bordercolor=surface, lightcolor=surface, darkcolor=surface)
        style.map(
            name,
            relief=[("pressed", "flat")],
            lightcolor=[("disabled", bg), ("!disabled", surface)],
            darkcolor=[("disabled", bg), ("!disabled", surface)],
            bordercolor=[("disabled", bg), ("focus", focus), ("!disabled", surface)],
        )
        # Keep semantic hover colors, adding a distinct pressed state before active.
        style.map(name, background=[("disabled", bg), ("pressed", field_bg), ("active", active), ("focus", active)])

    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            name,
            background=field_bg,
            bordercolor=border,
            lightcolor=field_bg,
            darkcolor=field_bg,
            arrowcolor=fg,
            insertcolor=fg,
            selectbackground=primary_bg,
            selectforeground="#ffffff",
        )
        style.map(
            name,
            background=[("disabled", bg), ("active", hover_bg), ("!disabled", field_bg)],
            lightcolor=[("focus", focus), ("!focus", field_bg)],
            darkcolor=[("focus", focus), ("!focus", field_bg)],
            bordercolor=[("disabled", border), ("focus", focus), ("!focus", border)],
            arrowcolor=[("disabled", disabled_fg), ("!disabled", fg)],
        )

    style.configure("TLabelframe", borderwidth=0, relief="flat")
    # The native separator paints an etched line. A flat frame element gives
    # both orientations a thin muted divider instead of a white bevel.
    style.layout("TSeparator", [("Frame.border", {"sticky": "nswe"})])
    style.configure("TSeparator", background=border, borderwidth=0, relief="flat")
    style.configure("TNotebook", background=bg, borderwidth=0, lightcolor=bg, darkcolor=bg, bordercolor=bg)
    style.configure(
        "TNotebook.Tab",
        background=bg,
        foreground=fg,
        padding=(12, 6),
        bordercolor=bg,
        lightcolor=bg,
        darkcolor=bg,
        focuscolor=focus,
    )
    style.map(
        "TNotebook.Tab",
        background=[("disabled", bg), ("selected", field_bg), ("active", hover_bg), ("!selected", bg)],
        foreground=[("disabled", disabled_fg), ("selected", focus), ("!disabled", fg)],
        lightcolor=[("selected", field_bg), ("!selected", bg)],
        darkcolor=[("selected", field_bg), ("!selected", bg)],
        # Selection already has a filled surface and accent label. Do not add
        # a second square outline on focus; the native label focus cue stays.
        bordercolor=[("disabled", bg), ("selected", field_bg), ("!selected", bg)],
        padding=[("selected", (12, 6)), ("!selected", (12, 6))],
    )

    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            name,
            indicatorbackground=field_bg,
            indicatorforeground=fg,
            upperbordercolor=border,
            lowerbordercolor=border,
        )
        style.map(
            name,
            indicatorbackground=[("disabled", bg), ("pressed", hover_bg), ("selected", focus), ("alternate", hover_bg)],
            indicatorforeground=[("disabled", disabled_fg), ("selected", bg), ("!disabled", fg)],
            upperbordercolor=[("focus", focus), ("!focus", border)],
            lowerbordercolor=[("focus", focus), ("!focus", border)],
        )

    for name in ("TScale", "TScrollbar"):
        style.configure(
            name, background=button_bg, bordercolor=border, lightcolor=button_bg, darkcolor=button_bg, gripsize=0
        )
        style.map(
            name,
            background=[("disabled", bg), ("pressed", focus), ("active", hover_bg), ("!disabled", button_bg)],
            lightcolor=[("disabled", bg), ("!disabled", button_bg)],
            darkcolor=[("disabled", bg), ("!disabled", button_bg)],
        )
    # Clam shares slider background with the thumb, not the trough. Make the
    # thumb distinguishable from the field without restoring a raised grip.
    style.configure("TScale", background=focus, lightcolor=focus, darkcolor=focus)
    style.map(
        "TScale",
        background=[("disabled", bg), ("pressed", primary_bg), ("!disabled", focus)],
        lightcolor=[("disabled", bg), ("!disabled", focus)],
        darkcolor=[("disabled", bg), ("!disabled", focus)],
    )
