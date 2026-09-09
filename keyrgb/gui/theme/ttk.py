from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Literal

from . import metrics

logger = logging.getLogger(__name__)

_BG_COLOR = "#2b2b2b"
_FG_COLOR = "#e0e0e0"

# Centralized palette. Normal text targets WCAG 4.5:1 against its
# background/field; disabled text targets the project usability floor of
# 3:1 (not a WCAG conformance claim).
DARK_BG = _BG_COLOR
DARK_FG = _FG_COLOR
DARK_FIELD_BG = "#3a3a3a"
DARK_DISABLED_FG = "#9a9a9a"
DARK_FOCUS = "#7ab8ff"
DARK_BUTTON_BG = "#404040"
DARK_BUTTON_ACTIVE_BG = "#505050"
DARK_PRIMARY_BG = "#0b5cad"
DARK_PRIMARY_ACTIVE_BG = "#1565b8"
DARK_DESTRUCTIVE_BG = "#b71c1c"
DARK_DESTRUCTIVE_ACTIVE_BG = "#c62828"
DARK_ACTION_FG = "#ffffff"

LIGHT_DISABLED_FG = "#666666"
LIGHT_FOCUS = "#0b5cad"
LIGHT_PRIMARY_BG = "#0b5cad"
LIGHT_PRIMARY_ACTIVE_BG = "#1565b8"
LIGHT_DESTRUCTIVE_BG = "#b71c1c"
LIGHT_DESTRUCTIVE_ACTIVE_BG = "#c62828"
LIGHT_ACTION_FG = "#ffffff"
LIGHT_BUTTON_FALLBACK_BG = "#d9d9d9"

NORMAL_CONTRAST_TARGET = 4.5
DISABLED_CONTRAST_TARGET = 3.0
TITLE_CONTRAST_TARGET = 3.0

# Module-level references keep Tk named fonts alive for the process
# lifetime; otherwise Tk may garbage-collect unreferenced Font objects.
_FONT_REFS: dict[tuple[int, str], tkfont.Font] = {}


def apply_clam_light_theme(root: tk.Misc) -> tuple[str, str]:
    """Apply a light ttk theme based on ttk defaults.

    We keep styling minimal and derive colors from the active ttk theme so the
    appearance stays aligned with the user's environment.
    """

    style = ttk.Style(root)
    style.theme_use("clam")

    _apply_scaling_if_configured(root)

    bg_color = style.lookup("TFrame", "background") or style.lookup(".", "background")
    fg_color = style.lookup("TLabel", "foreground") or style.lookup(".", "foreground")
    if not bg_color:
        bg_color = "#f0f0f0"
    if not fg_color:
        fg_color = "#000000"

    try:
        root.configure(bg=bg_color)  # type: ignore[call-arg]
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Light theme could not set root background: %s", exc)

    field_bg = style.lookup("TEntry", "fieldbackground") or "#ffffff"
    button_bg = style.lookup("TButton", "background") or LIGHT_BUTTON_FALLBACK_BG

    fonts = ensure_theme_fonts(root)

    # Ensure container widgets pick up a consistent background.
    style.configure("TFrame", background=bg_color)
    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("TLabelframe", background=bg_color, foreground=fg_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
    style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

    style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TCombobox", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TSpinbox", fieldbackground=field_bg, foreground=fg_color)

    trough = style.lookup("TScale", "troughcolor") or field_bg
    style.configure("TScale", background=bg_color, troughcolor=trough)
    style.configure("TScrollbar", background=bg_color, troughcolor=trough)

    _apply_state_maps(
        style,
        bg=bg_color,
        fg=fg_color,
        field_bg=field_bg,
        disabled_fg=LIGHT_DISABLED_FG,
        focus_color=LIGHT_FOCUS,
        button_active_bg=button_bg,
        button_disabled_bg=bg_color,
    )

    # Checkbutton styling is centralized.
    style.configure("TCheckbutton", background=bg_color, foreground=fg_color)

    _apply_semantic_styles(
        style,
        bg=bg_color,
        fg=fg_color,
        disabled_fg=LIGHT_DISABLED_FG,
        focus_color=LIGHT_FOCUS,
        primary_bg=LIGHT_PRIMARY_BG,
        primary_active_bg=LIGHT_PRIMARY_ACTIVE_BG,
        destructive_bg=LIGHT_DESTRUCTIVE_BG,
        destructive_active_bg=LIGHT_DESTRUCTIVE_ACTIVE_BG,
        action_fg=LIGHT_ACTION_FG,
        fonts=fonts,
    )

    return bg_color, fg_color


def apply_clam_dark_theme(root: tk.Misc) -> tuple[str, str]:
    """Apply the common KeyRGB dark ttk theme.

    This centralizes styling so individual windows stay small and consistent.
    Returns (bg_color, fg_color).
    """

    style = ttk.Style(root)
    style.theme_use("clam")

    _apply_scaling_if_configured(root)

    bg_color = _BG_COLOR
    fg_color = _FG_COLOR

    try:
        root.configure(bg=bg_color)  # type: ignore[call-arg]
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Dark theme could not set root background: %s", exc)

    fonts = ensure_theme_fonts(root)

    style.configure("TFrame", background=bg_color)
    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("TButton", background=DARK_BUTTON_BG, foreground=fg_color)

    # Container widgets
    style.configure("TLabelframe", background=bg_color, foreground=fg_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
    style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

    # Common input widgets (avoid bright default field backgrounds)
    field_bg = DARK_FIELD_BG
    style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TCombobox", fieldbackground=field_bg, foreground=fg_color)
    style.configure("TSpinbox", fieldbackground=field_bg, foreground=fg_color)

    # Sliders/scrollbars often have light troughs by default.
    style.configure("TScale", background=bg_color, troughcolor=field_bg)
    style.configure("TScrollbar", background=bg_color, troughcolor=field_bg)

    _apply_state_maps(
        style,
        bg=bg_color,
        fg=fg_color,
        field_bg=field_bg,
        disabled_fg=DARK_DISABLED_FG,
        focus_color=DARK_FOCUS,
        button_active_bg=DARK_BUTTON_ACTIVE_BG,
        button_disabled_bg=bg_color,
    )

    # Checkbutton styling is centralized.
    style.configure("TCheckbutton", background=bg_color, foreground=fg_color)

    _apply_semantic_styles(
        style,
        bg=bg_color,
        fg=fg_color,
        disabled_fg=DARK_DISABLED_FG,
        focus_color=DARK_FOCUS,
        primary_bg=DARK_PRIMARY_BG,
        primary_active_bg=DARK_PRIMARY_ACTIVE_BG,
        destructive_bg=DARK_DESTRUCTIVE_BG,
        destructive_active_bg=DARK_DESTRUCTIVE_ACTIVE_BG,
        action_fg=DARK_ACTION_FG,
        fonts=fonts,
    )

    return bg_color, fg_color


def ensure_theme_fonts(root: tk.Misc | None = None) -> dict[str, str]:
    """Create (or reuse) Tk named fonts for the semantic roles.

    Roles use absolute point sizes from
    :data:`keyrgb.gui.theme.metrics.FONT_SPECS` on the system-resolved
    ``Sans`` alias, preserving the established 14/11/10/9/8 hierarchy while
    staying in named fonts (Tk scaling and ``KEYRGB_TK_SCALING`` still apply
    because sizes are points, not pixels). ``TkDefaultFont`` is still read —
    with the supplied ``root`` — for interpreter availability and its valid
    slant, but its family/size are never inherited, so sessions reporting
    e.g. fixed 8 cannot collapse the hierarchy. The supplied ``root`` is
    forwarded to every :mod:`tkinter.font` call instead of relying on the
    implicit default root. Returned mapping is ``{style_name: font_name}``;
    it is empty when no Tk interpreter is available (headless unit tests).
    Created fonts are retained in ``_FONT_REFS`` so Tk does not
    garbage-collect them.
    """

    try:
        base = tkfont.nametofont("TkDefaultFont", root=root)
        base_actual = base.actual()
    except (tk.TclError, RuntimeError, ValueError) as exc:
        logger.debug("Theme fonts unavailable without TkDefaultFont: %s", exc)
        return {}
    base_slant_raw = base_actual.get("slant", "roman")
    slant: Literal["roman", "italic"] = base_slant_raw if base_slant_raw in ("roman", "italic") else "roman"

    configured: dict[str, str] = {}
    interpreter_id = id(getattr(root, "tk", None))
    for style_name, font_name in metrics.FONT_NAME_BY_STYLE.items():
        spec = metrics.FONT_SPECS.get(font_name)
        if spec is None:
            continue
        size, weight = spec
        cache_key = (interpreter_id, font_name)
        try:
            existing = _FONT_REFS.get(cache_key)
            if existing is None:
                try:
                    existing = tkfont.nametofont(font_name, root=root)
                except (tk.TclError, RuntimeError, ValueError):
                    existing = None
            if existing is not None:
                existing.configure(size=size, weight=weight, slant=slant, family=metrics.THEME_FONT_FAMILY)
                _FONT_REFS[cache_key] = existing
            else:
                created = tkfont.Font(
                    root=root,
                    name=font_name,
                    size=size,
                    weight=weight,
                    slant=slant,
                    family=metrics.THEME_FONT_FAMILY,
                )
                _FONT_REFS[cache_key] = created
            configured[style_name] = font_name
        except (tk.TclError, RuntimeError, ValueError) as exc:
            logger.debug("Theme font %s could not be configured: %s", font_name, exc)
            continue
    return configured


def _apply_state_maps(
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


def _apply_semantic_styles(
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


def _apply_scaling_if_configured(root: tk.Misc) -> None:
    scaling_raw = os.environ.get("KEYRGB_TK_SCALING")
    if not scaling_raw:
        return

    try:
        scaling = float(scaling_raw)
    except (TypeError, ValueError) as exc:
        logger.debug("Ignoring invalid KEYRGB_TK_SCALING=%r: %s", scaling_raw, exc)
        return

    if scaling <= 0:
        return

    try:
        root.tk.call("tk", "scaling", scaling)
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Tk scaling call failed for %r: %s", scaling, exc)
