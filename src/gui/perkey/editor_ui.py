from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.core import profiles
from src.gui.widgets.color_wheel import ColorWheel

from .canvas import KeyboardCanvas
from .overlay import OverlayControls


def build_editor_ui(editor) -> None:
    main = ttk.Frame(editor.root, padding=16)
    main.pack(fill="both", expand=True)

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
    right.pack_propagate(False)

    backdrop_row = ttk.Frame(right)
    backdrop_row.pack(fill="x", pady=(0, 10))
    ttk.Button(backdrop_row, text="Set Backdrop...", command=editor._set_backdrop).pack(
        side="left", fill="x", expand=True, padx=(0, 6)
    )
    ttk.Button(backdrop_row, text="Reset Backdrop", command=editor._reset_backdrop).pack(
        side="left", fill="x", expand=True
    )

    editor.status_label = ttk.Label(right, text="Click a key to start", font=("Sans", 9), width=32)
    editor.status_label.pack(pady=(0, 8))

    initial = editor._last_non_black_color
    editor.color_wheel = ColorWheel(
        right,
        size=editor._wheel_size,
        initial_color=initial,
        callback=editor._on_color_change,
        release_callback=editor._on_color_release,
    )
    editor.color_wheel.pack()

    apply_row = ttk.Frame(right)
    apply_row.pack(fill="x", pady=(8, 0))
    ttk.Checkbutton(
        apply_row,
        text="Apply to all keys",
        variable=editor.apply_all_keys,
    ).pack(anchor="w")

    btns = ttk.Frame(right)
    btns.pack(fill="x", pady=12)
    ttk.Button(btns, text="Fill All", command=editor._fill_all).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Clear All", command=editor._clear_all).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Run Keymap Calibrator", command=editor._run_calibrator).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Reload Keymap", command=editor._reload_keymap).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Overlay", command=editor._toggle_overlay).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Profiles", command=editor._toggle_profiles).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Close", command=editor.root.destroy).pack(fill="x")

    extras = ttk.Frame(left)
    extras.grid(row=1, column=0, sticky="ew", pady=(12, 0))
    extras.columnconfigure(0, weight=1)
    extras.columnconfigure(1, weight=0)
    extras.columnconfigure(2, weight=0)

    extras_profiles = ttk.Frame(extras)
    extras_profiles.grid(row=0, column=1, sticky="ns", padx=(0, 16))
    extras_overlay = ttk.Frame(extras)
    extras_overlay.grid(row=0, column=2, sticky="ne")

    editor._profiles_frame = ttk.LabelFrame(extras_profiles, text="Profiles", padding=10)
    editor._profiles_frame.grid(row=0, column=0, sticky="ns")
    editor._profiles_frame.grid_remove()
    extras_profiles.columnconfigure(0, weight=1)
    editor._profiles_frame.columnconfigure(1, weight=1)

    ttk.Label(editor._profiles_frame, text="Profile").grid(row=0, column=0, sticky="w")
    editor._profiles_combo = ttk.Combobox(
        editor._profiles_frame,
        textvariable=editor._profile_name_var,
        values=profiles.list_profiles(),
        width=22,
    )
    editor._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    pbtns = ttk.Frame(editor._profiles_frame)
    pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    pbtns.columnconfigure(0, weight=1)
    pbtns.columnconfigure(1, weight=1)
    pbtns.columnconfigure(2, weight=1)

    ttk.Button(pbtns, text="Activate", command=editor._activate_profile).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(pbtns, text="Save", command=editor._save_profile).grid(row=0, column=1, sticky="ew", padx=(0, 6))
    ttk.Button(pbtns, text="Delete", command=editor._delete_profile).grid(row=0, column=2, sticky="ew")

    editor.overlay_controls = OverlayControls(extras_overlay, editor=editor)
    editor.overlay_controls.grid(row=0, column=0, sticky="ne")
    # Hidden by default (toggled by the Overlay button)
    editor.overlay_controls.grid_remove()
    editor.overlay_controls.sync_vars_from_scope()
