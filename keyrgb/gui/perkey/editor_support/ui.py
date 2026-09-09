from __future__ import annotations

# @quality-exception file-size-analysis: single build_editor_ui builder for the per-key editor chrome
import tkinter as tk
from tkinter import TclError, ttk

from keyrgb.gui.perkey.ui import _profile_actions_ui as profile_action_ui
from keyrgb.gui.theme import metrics as theme_metrics
from keyrgb.gui.theme.focus import schedule_initial_focus
from keyrgb.gui.widgets.color_wheel import ColorWheel

from ..canvas import KeyboardCanvas
from ..lightbar_controls import LightbarControls
from ..overlay import OverlayControls
from ..ui.layout_setup import LayoutSetupControls, OptionalKeysControls
from ..ui.lighting_areas import LightingAreasPanel
from ..ui.responsive_columns import ResponsiveEntry, install_responsive_columns

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


def build_editor_ui(editor) -> None:
    main = ttk.Frame(editor.root, padding=theme_metrics.OUTER_PADDING)
    main.pack(fill="both", expand=True)

    status_row = ttk.Frame(main)
    status_row.pack(fill="x", pady=(0, 10))

    editor.status_label = ttk.Label(
        status_row,
        text="Click a key to start",
        style=theme_metrics.STATUS_LABEL_STYLE,
        anchor="w",
        justify="left",
    )
    editor.status_label.pack(side="left", fill="x", expand=True)

    # UX-03 visible unsaved indicator: compact pill beside the status text.
    editor._unsaved_label = ttk.Label(
        status_row,
        text="Saved",
        style=theme_metrics.STATUS_LABEL_STYLE,
        anchor="e",
        justify="right",
    )
    editor._unsaved_label.pack(side="right", padx=(8, 0))

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
    backdrop_row.pack(fill="x", pady=(0, theme_metrics.CONTROL_GAP_Y))
    backdrop_row.columnconfigure(1, weight=1)
    ttk.Label(backdrop_row, text="Backdrop", style=theme_metrics.BODY_LABEL_STYLE).grid(row=0, column=0, sticky="w")
    _backdrop_mode_label_list = [_BACKDROP_MODE_LABELS[m] for m in ("none", "builtin", "custom")]
    editor._backdrop_mode_combo = ttk.Combobox(
        backdrop_row,
        state="readonly",
        width=16,
        values=_backdrop_mode_label_list,
    )
    editor._backdrop_mode_combo.set(_BACKDROP_MODE_LABELS.get(editor._backdrop_mode_var.get(), "Built-in seed"))
    editor._backdrop_mode_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
    editor._backdrop_mode_combo.bind(
        "<<ComboboxSelected>>",
        lambda _e: _set_backdrop_mode_from_label(editor, editor._backdrop_mode_combo.get()),
    )

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
    ).pack(anchor="w", pady=(theme_metrics.CONTROL_GAP_Y, 0))

    btns = ttk.Frame(right)
    btns.pack(fill="x", pady=12)

    def _divider(parent: ttk.Frame, title: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 6))
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=title, style=theme_metrics.SECTION_LABEL_STYLE).grid(row=0, column=0, sticky="w")
        ttk.Separator(row, orient="horizontal").grid(row=0, column=1, sticky="ew", padx=(8, 0))

    _divider(btns, "Config")
    ttk.Button(btns, text="Fill All", command=editor._fill_all).pack(fill="x", pady=(0, theme_metrics.CONTROL_GAP_Y))
    ttk.Button(
        btns,
        text="Clear All",
        command=editor._clear_all,
        style=theme_metrics.DESTRUCTIVE_BUTTON_STYLE,
    ).pack(fill="x", pady=(0, theme_metrics.CONTROL_GAP_Y))

    # UX-03 editor shell: notebook below the top content spans canvas+rail
    # full width. Tabs are Profiles, Setup, Advanced in that order.
    editor._editor_notebook = ttk.Notebook(main)
    editor._editor_notebook.pack(fill="x", pady=(12, 0))

    editor._profiles_tab = ttk.Frame(editor._editor_notebook)
    editor._setup_tab = ttk.Frame(editor._editor_notebook)
    editor._advanced_tab = ttk.Frame(editor._editor_notebook)
    editor._editor_notebook.add(editor._profiles_tab, text="Profiles")
    editor._editor_notebook.add(editor._setup_tab, text="Setup")
    editor._editor_notebook.add(editor._advanced_tab, text="Advanced")
    editor._profiles_tab.columnconfigure(0, weight=1)
    editor._profiles_tab.columnconfigure(1, weight=1)
    editor._setup_tab.columnconfigure(0, weight=1)
    editor._setup_tab.columnconfigure(1, weight=1)
    editor._advanced_tab.columnconfigure(0, weight=1)
    editor._advanced_tab.columnconfigure(1, weight=1)

    def _on_editor_tab_changed(_event: object) -> None:
        try:
            selected_index = int(editor._editor_notebook.index(editor._editor_notebook.select()))
        except _STATUS_WRAP_SYNC_ERRORS:
            return
        # Guard against re-entrant select() events: programmatic
        # _show_setup_panel() re-selects the same tab, which may emit
        # <<NotebookTabChanged>> again. Skip the redundant sync.
        if selected_index == 1:
            if vars(editor).get("_setup_panel_mode") == "layout":
                return
            editor._show_setup_panel("layout")
        elif selected_index == 2:
            if vars(editor).get("_setup_panel_mode") == "overlay":
                return
            editor._show_setup_panel("overlay")
        else:
            editor._setup_panel_mode = None

    try:
        editor._editor_notebook.bind("<<NotebookTabChanged>>", _on_editor_tab_changed, add="+")
    except _TK_CALLBACK_SETUP_ERRORS:
        pass

    # UX-03 refinement: tab interiors use two side-by-side columns when wide
    # so controls no longer stretch across ~1500px; narrow tabs stack.
    editor._profiles_frame = ttk.LabelFrame(editor._profiles_tab, text="Lighting profiles", padding=10)
    editor._profiles_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    editor._profiles_frame.columnconfigure(1, weight=1)
    editor._profiles_auto_frame = ttk.LabelFrame(editor._profiles_tab, text="Automatic selection", padding=10)
    editor._profiles_auto_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    editor._profiles_auto_frame.columnconfigure(1, weight=1)

    ttk.Label(editor._profiles_frame, text="Lighting profile").grid(row=0, column=0, sticky="w")
    # Single shared scan at construction, cached on the editor: no
    # filesystem/profile scan on popup open or later policy saves.
    profile_names_snapshot = profile_action_ui.refresh_profile_snapshot(editor)
    editor._profiles_combo = ttk.Combobox(
        editor._profiles_frame,
        textvariable=editor._profile_name_var,
        values=list(profile_names_snapshot),
        width=22,
        state="readonly",
    )
    editor._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    pbtns = ttk.Frame(editor._profiles_frame)
    pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    pbtns.columnconfigure(0, weight=1)
    pbtns.columnconfigure(1, weight=1)
    pbtns.columnconfigure(2, weight=1)
    pbtns.columnconfigure(3, weight=1)

    ttk.Button(pbtns, text="New", command=editor._new_profile).grid(row=0, column=0, sticky="ew", padx=(0, 3))
    ttk.Button(pbtns, text="Activate", command=editor._activate_profile).grid(row=0, column=1, sticky="ew", padx=(3, 3))
    ttk.Button(
        pbtns,
        text="Save",
        command=editor._save_profile,
        style=theme_metrics.PRIMARY_BUTTON_STYLE,
    ).grid(row=0, column=2, sticky="ew", padx=(3, 3))
    ttk.Button(
        pbtns,
        text="Delete",
        command=editor._delete_profile,
        style=theme_metrics.DESTRUCTIVE_BUTTON_STYLE,
    ).grid(row=0, column=3, sticky="ew", padx=(3, 0))

    ttk.Button(
        editor._profiles_auto_frame,
        text="Set as Default",
        command=editor._set_default_profile,
    ).grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="ew",
    )

    ttk.Label(editor._profiles_auto_frame, text="Use on AC").grid(row=1, column=0, sticky="w", pady=(10, 0))
    editor._ac_power_source_profile_combo = ttk.Combobox(
        editor._profiles_auto_frame,
        textvariable=editor._ac_power_source_profile_var,
        width=22,
        state="readonly",
    )
    editor._ac_power_source_profile_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))
    editor._ac_power_source_profile_combo.bind(
        "<<ComboboxSelected>>", lambda _e: editor._save_power_source_profile_policy()
    )

    ttk.Label(editor._profiles_auto_frame, text="Use on battery").grid(row=2, column=0, sticky="w", pady=(8, 0))
    editor._battery_power_source_profile_combo = ttk.Combobox(
        editor._profiles_auto_frame,
        textvariable=editor._battery_power_source_profile_var,
        width=22,
        state="readonly",
    )
    editor._battery_power_source_profile_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
    editor._battery_power_source_profile_combo.bind(
        "<<ComboboxSelected>>",
        lambda _e: editor._save_power_source_profile_policy(),
    )
    profile_action_ui.sync_power_source_profile_policy_controls(editor, profile_names_snapshot)
    install_responsive_columns(
        editor._profiles_tab,
        [
            ResponsiveEntry(
                widget=editor._profiles_frame,
                wide={"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)},
                narrow={"row": 0, "column": 0, "columnspan": 2, "sticky": "nsew"},
            ),
            ResponsiveEntry(
                widget=editor._profiles_auto_frame,
                wide={"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)},
                narrow={"row": 1, "column": 0, "columnspan": 2, "sticky": "nsew", "pady": (10, 0)},
            ),
        ],
    )

    editor._layout_setup_controls = LayoutSetupControls(editor._setup_tab, editor=editor)
    editor._layout_setup_controls.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    editor._optional_keys_controls = OptionalKeysControls(editor._setup_tab, editor=editor)
    editor._optional_keys_controls.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    editor._run_calibrator_button = ttk.Button(
        editor._setup_tab,
        text="Run Keymap Calibrator",
        command=editor._run_calibrator,
    )
    editor._run_calibrator_button.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(10, 0))
    install_responsive_columns(
        editor._setup_tab,
        [
            ResponsiveEntry(
                widget=editor._layout_setup_controls,
                wide={"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)},
                narrow={"row": 0, "column": 0, "columnspan": 2, "sticky": "nsew"},
            ),
            ResponsiveEntry(
                widget=editor._optional_keys_controls,
                wide={"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)},
                narrow={"row": 1, "column": 0, "columnspan": 2, "sticky": "nsew", "pady": (10, 0)},
            ),
            ResponsiveEntry(
                widget=editor._run_calibrator_button,
                wide={"row": 1, "column": 1, "sticky": "ew", "padx": (6, 0), "pady": (10, 0)},
                narrow={"row": 2, "column": 0, "columnspan": 2, "sticky": "ew", "pady": (10, 0)},
            ),
        ],
    )

    editor._advanced_backdrop_frame = ttk.LabelFrame(editor._advanced_tab, text="Backdrop", padding=10)
    editor._advanced_backdrop_frame.columnconfigure(0, weight=1)
    editor._advanced_backdrop_frame.columnconfigure(1, weight=1)
    ttk.Button(
        editor._advanced_backdrop_frame,
        text="Set Backdrop...",
        command=editor._set_backdrop,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(
        editor._advanced_backdrop_frame,
        text="Reset Backdrop",
        command=editor._reset_backdrop,
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
    ttk.Label(
        editor._advanced_backdrop_frame,
        text="Backdrop transparency",
        style=theme_metrics.BODY_LABEL_STYLE,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
    ttk.Scale(
        editor._advanced_backdrop_frame,
        from_=0,
        to=100,
        orient="horizontal",
        variable=editor.backdrop_transparency,
        command=editor._on_backdrop_transparency_changed,
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    editor._overlay_setup_panel = ttk.Frame(editor._advanced_tab)
    editor._overlay_setup_panel.columnconfigure(0, weight=1)

    editor.overlay_controls = OverlayControls(editor._overlay_setup_panel, editor=editor)
    editor.overlay_controls.grid(row=0, column=0, sticky="nsew")

    editor.lightbar_controls = None
    if bool(getattr(editor, "has_lightbar_device", False)):
        editor.lightbar_controls = LightbarControls(editor._overlay_setup_panel, editor=editor)
        editor.lightbar_controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    editor._lighting_areas_panel = LightingAreasPanel(editor._advanced_tab, editor=editor, tk_module=tk, ttk_module=ttk)
    # Stable two-column Advanced layout regardless of visibility: backdrop
    # left row 0, overlay/tools right row 0, lighting areas right row 1.
    # A later sync_from_editor() re-show (grid() with no args) therefore
    # lands below the overlay instead of overlapping it, even when lighting
    # availability changes without a resize. The responsive helper keeps
    # the hidden stored options in sync so narrow re-shows stack.
    editor._lighting_areas_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(10, 0))
    if not editor._lighting_areas_panel.should_show:
        editor._lighting_areas_panel.grid_remove()
    editor._advanced_backdrop_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    editor._overlay_setup_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    lighting_panel = editor._lighting_areas_panel
    install_responsive_columns(
        editor._advanced_tab,
        [
            ResponsiveEntry(
                widget=editor._advanced_backdrop_frame,
                wide={"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)},
                narrow={"row": 0, "column": 0, "columnspan": 2, "sticky": "nsew"},
            ),
            ResponsiveEntry(
                widget=editor._overlay_setup_panel,
                wide={"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)},
                narrow={"row": 1, "column": 0, "columnspan": 2, "sticky": "nsew", "pady": (10, 0)},
            ),
            ResponsiveEntry(
                widget=lighting_panel,
                wide={"row": 1, "column": 1, "sticky": "nsew", "padx": (6, 0), "pady": (10, 0)},
                narrow={"row": 2, "column": 0, "columnspan": 2, "sticky": "nsew", "pady": (10, 0)},
                is_hidden=lambda: not lighting_panel.should_show,
                record_hidden=lighting_panel.record_hidden_placement,
            ),
        ],
    )

    editor.overlay_controls.sync_vars_from_scope()
    if editor.lightbar_controls is not None:
        editor.lightbar_controls.sync_vars_from_editor()

    # Intentional non-forcing initial focus (UX-05): the backdrop selector is
    # the first keyboard-operable control and always exists. The helper
    # schedules via `after`, never grabs, and never steals an already-focused
    # child. Keymap refresh after calibration is tied to calibrator process
    # completion, so ordinary focus movement performs no profile I/O.
    schedule_initial_focus(editor.root, editor._backdrop_mode_combo)
