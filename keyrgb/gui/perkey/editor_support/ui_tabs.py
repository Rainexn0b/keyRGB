from __future__ import annotations

from keyrgb.gui.perkey.ui import _profile_actions_ui as profile_action_ui
from keyrgb.gui.perkey.ui.responsive_columns import ResponsiveEntry, install_responsive_columns
from keyrgb.gui.theme import metrics as theme_metrics

from .ui_common import _STATUS_WRAP_SYNC_ERRORS, _TK_CALLBACK_SETUP_ERRORS


def build_tabs(editor, main, *, ttk, LayoutSetupControls, OptionalKeysControls) -> None:
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

    ttk.Button(pbtns, text="New", command=editor._new_profile).grid(row=0, column=0, sticky="ew", padx=(0, 3))
    ttk.Button(pbtns, text="Activate", command=editor._activate_profile).grid(row=0, column=1, sticky="ew", padx=(3, 0))
    ttk.Button(
        pbtns,
        text="Save",
        command=editor._save_profile,
        style=theme_metrics.PRIMARY_BUTTON_STYLE,
    ).grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
    ttk.Button(
        pbtns,
        text="Delete",
        command=editor._delete_profile,
        style=theme_metrics.DESTRUCTIVE_BUTTON_STYLE,
    ).grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))

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
    editor._guided_setup_button = ttk.Button(
        editor._setup_tab,
        text="Guided Setup…",
        command=editor._open_guided_setup,
    )
    editor._guided_setup_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(10, 0))
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
                widget=editor._guided_setup_button,
                wide={"row": 1, "column": 0, "sticky": "ew", "padx": (0, 6), "pady": (10, 0)},
                narrow={"row": 2, "column": 0, "columnspan": 2, "sticky": "ew", "pady": (10, 0)},
            ),
            ResponsiveEntry(
                widget=editor._run_calibrator_button,
                wide={"row": 1, "column": 1, "sticky": "ew", "padx": (6, 0), "pady": (10, 0)},
                narrow={"row": 3, "column": 0, "columnspan": 2, "sticky": "ew", "pady": (8, 0)},
            ),
        ],
    )
