from __future__ import annotations

import tkinter as tk
from tkinter import TclError, ttk

from src.core.profile import profiles
from src.gui.widgets.color_wheel import ColorWheel
from src.gui.widgets.dropdown import UpwardListboxDropdown

from ..canvas import KeyboardCanvas
from ..lightbar_controls import LightbarControls
from ..overlay import OverlayControls
from ..ui.layout_setup import LayoutSetupControls


_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}

_STATUS_WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, TclError, TypeError, ValueError)
_TK_CALLBACK_SETUP_ERRORS = (RuntimeError, TclError)


def _set_backdrop_mode_from_label(editor, label: str) -> None:
    for mode, mode_label in _BACKDROP_MODE_LABELS.items():
        if mode_label == label:
            editor._backdrop_mode_var.set(mode)
            break
    else:
        editor._backdrop_mode_var.set("builtin")
    editor._on_backdrop_mode_changed()


def _apply_backdrop_mode_dropdown_value(editor, label: str) -> None:
    """Update the backdrop combobox display and apply the chosen mode."""
    try:
        editor._backdrop_mode_combo.set(label)
    except _TK_CALLBACK_SETUP_ERRORS:
        pass
    _set_backdrop_mode_from_label(editor, label)


def build_editor_ui(editor) -> None:
    main = ttk.Frame(editor.root, padding=16)
    main.pack(fill="both", expand=True)

    status_row = ttk.Frame(main)
    status_row.pack(fill="x", pady=(0, 10))

    editor.status_label = ttk.Label(
        status_row,
        text="Click a key to start",
        font=("Sans", 9),
        anchor="w",
        justify="left",
    )
    editor.status_label.pack(fill="x")

    def _sync_status_wrap(_e=None) -> None:
        try:
            width = int(status_row.winfo_width())
            editor.status_label.configure(wraplength=max(200, width - 8))
        except _STATUS_WRAP_SYNC_ERRORS:
            return

    try:
        editor.root.bind("<Configure>", _sync_status_wrap, add=True)
    except _TK_CALLBACK_SETUP_ERRORS:
        pass
    editor.root.after(0, _sync_status_wrap)

    content = ttk.Frame(main)
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)
    content.columnconfigure(1, weight=0)
    content.rowconfigure(0, weight=1)

    left = ttk.Frame(content)
    left.grid(row=0, column=0, sticky="nsew")
    left.columnconfigure(0, weight=1)
    left.rowconfigure(0, weight=1)
    left.rowconfigure(1, weight=0)

    canvas_frame = ttk.Frame(left)
    canvas_frame.grid(row=0, column=0, sticky="nsew")

    editor.canvas = KeyboardCanvas(
        canvas_frame,
        editor=editor,
        bg=editor.bg_color,
        highlightthickness=0,
    )
    editor.canvas.pack(side=tk.LEFT, fill="both", expand=True)

    right = ttk.Frame(content, width=editor._right_panel_width)
    right.grid(row=0, column=1, sticky="ns", padx=(16, 0))

    backdrop_row = ttk.Frame(right)
    backdrop_row.pack(fill="x", pady=(0, 6))
    backdrop_row.columnconfigure(1, weight=1)
    ttk.Label(backdrop_row, text="Backdrop", font=("Sans", 9)).grid(row=0, column=0, sticky="w")
    _backdrop_mode_label_list = [_BACKDROP_MODE_LABELS[m] for m in ("none", "builtin", "custom")]
    editor._backdrop_mode_combo = ttk.Combobox(
        backdrop_row,
        state="readonly",
        width=16,
        values=_backdrop_mode_label_list,
    )
    editor._backdrop_mode_combo.set(_BACKDROP_MODE_LABELS.get(editor._backdrop_mode_var.get(), "Built-in seed"))
    editor._backdrop_mode_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
    editor._backdrop_mode_dropdown = UpwardListboxDropdown(
        root=editor.root,
        anchor=editor._backdrop_mode_combo,
        values_provider=lambda: _backdrop_mode_label_list,
        get_current_value=lambda: editor._backdrop_mode_combo.get(),
        set_value=lambda label: _apply_backdrop_mode_dropdown_value(editor, label),
        bg=getattr(editor, "bg_color", "#2b2b2b"),
        fg=getattr(editor, "fg_color", "#ffffff"),
    )
    editor._backdrop_mode_combo.bind("<Button-1>", editor._backdrop_mode_dropdown.open)
    editor._backdrop_mode_combo.bind("<Down>", editor._backdrop_mode_dropdown.open)

    backdrop_buttons = ttk.Frame(right)
    backdrop_buttons.pack(fill="x", pady=(0, 10))
    backdrop_buttons.columnconfigure(0, weight=1)
    backdrop_buttons.columnconfigure(1, weight=1)
    ttk.Button(backdrop_buttons, text="Set Backdrop...", command=editor._set_backdrop).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 6),
    )
    ttk.Button(backdrop_buttons, text="Reset Backdrop", command=editor._reset_backdrop).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=(6, 0),
    )

    ttk.Label(right, text="Backdrop transparency", font=("Sans", 9)).pack(anchor="w", pady=(0, 4))
    ttk.Scale(
        right,
        from_=0,
        to=100,
        orient="horizontal",
        variable=editor.backdrop_transparency,
        command=editor._on_backdrop_transparency_changed,
    ).pack(fill="x", pady=(0, 10))

    initial = editor._last_non_black_color
    editor.color_wheel = ColorWheel(
        right,
        size=editor._wheel_size,
        initial_color=initial,
        callback=editor._on_color_change,
        release_callback=editor._on_color_release,
        show_rgb_label=False,
    )
    editor.color_wheel.pack()

    def _sync_right_panel_width() -> None:
        try:
            required_width = max(
                int(editor._right_panel_width),
                *(int(child.winfo_reqwidth()) for child in right.winfo_children()),
            )
        except _STATUS_WRAP_SYNC_ERRORS:
            return

        if required_width <= int(editor._right_panel_width):
            return

        editor._right_panel_width = required_width
        try:
            right.configure(width=required_width)
        except _STATUS_WRAP_SYNC_ERRORS:
            return

    # Some themes/font scales make the embedded ColorWheel request more width than
    # the legacy fixed panel; expand to the real requested width after layout.
    editor.root.after(0, _sync_right_panel_width)

    apply_row = ttk.Frame(right)
    apply_row.pack(fill="x", pady=(8, 0))
    ttk.Checkbutton(
        apply_row,
        text="Apply to all keys",
        variable=editor.apply_all_keys,
    ).pack(anchor="w")

    ttk.Checkbutton(
        apply_row,
        text="Sample tool",
        variable=editor.sample_tool_enabled,
        command=editor._on_sample_tool_toggled,
    ).pack(anchor="w", pady=(6, 0))

    btns = ttk.Frame(right)
    btns.pack(fill="x", pady=12)

    def _divider(parent: ttk.Frame, title: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 6))
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=title, font=("Sans", 9)).grid(row=0, column=0, sticky="w")
        ttk.Separator(row, orient="horizontal").grid(row=0, column=1, sticky="ew", padx=(8, 0))

    _divider(btns, "Config")
    ttk.Button(btns, text="Fill All", command=editor._fill_all).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Clear All", command=editor._clear_all).pack(fill="x", pady=(0, 6))

    _divider(btns, "Setup")
    ttk.Button(btns, text="1. Keyboard Setup", command=editor._toggle_layout_setup).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="2. Keymap Calibrator", command=editor._run_calibrator).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="3. Overlay Alignment", command=editor._toggle_overlay).pack(fill="x", pady=(0, 6))

    extras = ttk.Frame(left)
    extras.grid(row=1, column=0, sticky="ew", pady=(12, 0))
    extras.rowconfigure(0, weight=1)
    extras.columnconfigure(0, weight=1, uniform="perkey_bottom")
    extras.columnconfigure(1, weight=1, uniform="perkey_bottom")

    extras_profiles = ttk.Frame(extras)
    extras_profiles.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    extras_setup = ttk.Frame(extras)
    extras_setup.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    extras_profiles.columnconfigure(0, weight=1)
    extras_setup.columnconfigure(0, weight=1)

    editor._profiles_frame = ttk.LabelFrame(extras_profiles, text="Lighting profiles", padding=10)
    editor._profiles_frame.grid(row=0, column=0, sticky="nsew")
    editor._profiles_frame.columnconfigure(1, weight=1)

    ttk.Label(editor._profiles_frame, text="Lighting profile").grid(row=0, column=0, sticky="w")
    editor._profiles_combo = ttk.Combobox(
        editor._profiles_frame,
        textvariable=editor._profile_name_var,
        values=profiles.list_profiles(),
        width=22,
        state="readonly",
    )
    editor._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    editor._profiles_dropdown = UpwardListboxDropdown(
        root=editor.root,
        anchor=editor._profiles_combo,
        values_provider=profiles.list_profiles,
        get_current_value=lambda: editor._profile_name_var.get(),
        set_value=lambda value: editor._profile_name_var.set(value),
        bg=getattr(editor, "bg_color", "#2b2b2b"),
        fg=getattr(editor, "fg_color", "#ffffff"),
    )

    editor._profiles_combo.bind("<Button-1>", editor._profiles_dropdown.open)
    editor._profiles_combo.bind("<Down>", editor._profiles_dropdown.open)

    pbtns = ttk.Frame(editor._profiles_frame)
    pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    pbtns.columnconfigure(0, weight=1)
    pbtns.columnconfigure(1, weight=1)
    pbtns.columnconfigure(2, weight=1)
    pbtns.columnconfigure(3, weight=1)

    ttk.Button(pbtns, text="New", command=editor._new_profile).grid(row=0, column=0, sticky="ew", padx=(0, 3))
    ttk.Button(pbtns, text="Activate", command=editor._activate_profile).grid(row=0, column=1, sticky="ew", padx=(3, 3))
    ttk.Button(pbtns, text="Save", command=editor._save_profile).grid(row=0, column=2, sticky="ew", padx=(3, 3))
    ttk.Button(pbtns, text="Delete", command=editor._delete_profile).grid(row=0, column=3, sticky="ew", padx=(3, 0))

    ttk.Button(
        editor._profiles_frame,
        text="Set as Default",
        command=editor._set_default_profile,
    ).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="ew",
        pady=(8, 0),
    )

    editor._layout_setup_controls = LayoutSetupControls(extras_setup, editor=editor)
    editor._layout_setup_controls.grid(row=0, column=0, sticky="nsew")
    editor._layout_setup_controls.grid_remove()

    editor._overlay_setup_panel = ttk.Frame(extras_setup)
    editor._overlay_setup_panel.grid(row=0, column=0, sticky="nsew")
    editor._overlay_setup_panel.columnconfigure(0, weight=1)
    editor._overlay_setup_panel.grid_remove()

    editor.overlay_controls = OverlayControls(editor._overlay_setup_panel, editor=editor)
    editor.overlay_controls.grid(row=0, column=0, sticky="nsew")

    editor.lightbar_controls = None
    if bool(getattr(editor, "has_lightbar_device", False)):
        editor.lightbar_controls = LightbarControls(editor._overlay_setup_panel, editor=editor)
        editor.lightbar_controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    editor.overlay_controls.sync_vars_from_scope()
    if editor.lightbar_controls is not None:
        editor.lightbar_controls.sync_vars_from_editor()
