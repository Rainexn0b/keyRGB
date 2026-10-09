"""Hardware-free checks of actual clam element/state resolution.

These run when a Tk display is available; headless CI still exercises the
configuration and focus contracts in test_theme_ttk_unit.py.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from keyrgb.gui.perkey.editor_support.ui_tabs import _make_editor_tab
from keyrgb.gui.theme import metrics, ttk as theme


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def test_dark_surfaces_resolve_without_stock_bevels(root) -> None:
    theme.apply_clam_dark_theme(root)
    style = ttk.Style(root)
    for name in ("TButton", *metrics.SEMANTIC_BUTTON_STYLES):
        assert style.lookup(name, "relief") == "flat"
        for state in ((), ("active",), ("pressed",), ("disabled",)):
            assert style.lookup(name, "lightcolor", state).startswith("#")
            assert style.lookup(name, "lightcolor", state) not in ("#eeebe7", "#bab5ab")
            assert style.lookup(name, "darkcolor", state) not in ("#cfcdc8", "#bab5ab")
        assert style.lookup(name, "bordercolor", ("focus",)) == theme.DARK_FOCUS
        assert style.lookup(name, "foreground", ("disabled", "active")) == theme.DARK_DISABLED_FG
        assert style.lookup(name, "background", ("pressed", "active")) == theme.DARK_FIELD_BG
    assert str(style.lookup("TLabelframe", "borderwidth")) == "0"
    assert style.lookup("TNotebook.Tab", "background", ("selected",)) == theme.DARK_FIELD_BG
    assert style.lookup("TNotebook.Tab", "foreground", ("selected",)) == theme.DARK_FOCUS
    assert style.lookup("TNotebook.Tab", "lightcolor", ("selected",)) == theme.DARK_FIELD_BG
    assert style.lookup("TNotebook.Tab", "bordercolor", ("selected", "focus")) == theme.DARK_FIELD_BG
    assert style.lookup("TNotebook.Tab", "bordercolor", ("focus",)) == theme.DARK_BG
    assert style.lookup("TNotebook.Tab", "focuscolor", ("selected", "focus")) == theme.DARK_FOCUS
    assert "Notebook.focus" in str(style.layout("TNotebook.Tab"))


def test_inputs_indicators_and_both_slider_orientations_keep_focus_and_disabled_states(root) -> None:
    theme.apply_clam_dark_theme(root)
    style = ttk.Style(root)
    for name in ("TEntry", "TCombobox", "TSpinbox", "Horizontal.TScale", "Vertical.TScale"):
        assert style.lookup(name, "bordercolor") == theme.DARK_BORDER
        assert style.lookup(name, "bordercolor", ("focus",)) == theme.DARK_FOCUS
    assert style.lookup("TCombobox", "fieldbackground", ("readonly",)) == theme.DARK_FIELD_BG
    assert style.lookup("TCombobox", "arrowcolor", ("disabled",)) == theme.DARK_DISABLED_FG
    for name in ("TCheckbutton", "TRadiobutton"):
        assert style.lookup(name, "indicatorbackground") == theme.DARK_FIELD_BG
        assert style.lookup(name, "indicatorbackground", ("selected",)) == theme.DARK_FOCUS
        assert style.lookup(name, "indicatorbackground", ("disabled", "selected")) == theme.DARK_BG
        assert style.lookup(name, "upperbordercolor", ("focus",)) == theme.DARK_FOCUS
    # Native layouts/bindings stay intact: keyboard users can still move sliders.
    slider = ttk.Scale(root)
    assert slider.cget("takefocus") != "0"
    assert "Horizontal.Scale.slider" in str(style.layout("Horizontal.TScale"))


def test_dark_theme_does_not_pollute_light_theme_and_can_be_reapplied(root) -> None:
    style = ttk.Style(root)
    theme.apply_clam_light_theme(root)
    original = {
        name: (style.configure(name), style.map(name))
        for name in ("TNotebook.Tab", "TButton", "TLabelframe", "TSeparator")
    }
    button_padding = style.lookup("TButton", "padding")
    button_width = style.lookup("TButton", "width")
    theme.apply_clam_dark_theme(root)
    assert style.lookup("TButton", "padding") == button_padding
    assert style.lookup("TButton", "width") == button_width
    theme.apply_clam_light_theme(root)
    assert style.theme_use() == "clam"
    for name, settings in original.items():
        assert (style.configure(name), style.map(name)) == settings
    theme.apply_clam_dark_theme(root)
    assert style.theme_use() == theme.DARK_THEME_NAME


def test_dividers_keep_both_orientations_without_a_beveled_element(root) -> None:
    theme.apply_clam_dark_theme(root)
    style = ttk.Style(root)
    horizontal = ttk.Separator(root, orient="horizontal")
    vertical = ttk.Separator(root, orient="vertical")
    root.update_idletasks()
    assert horizontal.winfo_reqheight() == 1
    assert vertical.winfo_reqwidth() == 1
    assert "Separator.separator" not in str(style.layout("Horizontal.TSeparator"))
    assert style.lookup("Horizontal.TSeparator", "background") == theme.DARK_BORDER


def test_preview_defaults_and_combobox_popup_match_palette_without_overriding_artwork(root) -> None:
    theme.apply_clam_dark_theme(root)
    preview = tk.Canvas(root)
    assert preview.cget("background") == theme.DARK_BG
    assert preview.cget("highlightbackground") == theme.DARK_BORDER
    artwork = tk.Canvas(root, bg="#123456", highlightthickness=0)
    assert artwork.cget("background") == "#123456"
    assert str(artwork.cget("highlightthickness")) == "0"
    combo = ttk.Combobox(root, values=("First", "Second"), state="readonly")
    popup = root.tk.call("ttk::combobox::PopdownWindow", str(combo))
    listbox = f"{popup}.f.l"
    assert root.tk.call(listbox, "cget", "-background") == theme.DARK_BG
    assert root.tk.call(listbox, "cget", "-foreground") == theme.DARK_FG
    theme.apply_clam_light_theme(root)
    light_preview = tk.Canvas(root)
    assert light_preview.cget("background") != theme.DARK_BG


@pytest.mark.parametrize("palette", ["dark", "light"])
def test_editor_tab_divider_is_one_pixel_full_width_and_clear_of_content(root, palette) -> None:
    getattr(theme, f"apply_clam_{palette}_theme")(root)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    tabs = [_make_editor_tab(notebook, ttk=ttk) for _ in range(3)]
    headings = []
    for tab, title in zip(tabs, ("Profiles", "Setup", "Advanced")):
        notebook.add(tab, text=title)
        heading = ttk.Label(tab, text="Panel heading")
        heading.grid(row=0, column=0)
        headings.append(heading)
    root.deiconify()
    style = ttk.Style(root)
    assert style.lookup(metrics.TAB_DIVIDER_FRAME_STYLE, "background") == "#707070"
    assert str(style.lookup(metrics.TAB_DIVIDER_FRAME_STYLE, "borderwidth")) == "0"
    for width in (640, 320):
        root.geometry(f"{width}x240")
        for tab, heading in zip(tabs, headings):
            notebook.select(tab)
            root.update()
            divider = next(
                child for child in tab.winfo_children() if child.cget("style") == metrics.TAB_DIVIDER_FRAME_STYLE
            )
            assert divider.winfo_height() == 1
            assert divider.winfo_width() == tab.winfo_width()
            assert divider.winfo_y() == 0
            assert heading.winfo_y() >= 6
