from __future__ import annotations

from keyrgb.gui.theme import metrics as theme_metrics

from .ui_common import (
    _BACKDROP_MODE_LABELS,
    _STATUS_WRAP_SYNC_ERRORS,
    _TK_CALLBACK_SETUP_ERRORS,
    _set_backdrop_mode_from_label,
)


def build_shell(editor, *, ttk, tk, KeyboardCanvas, ColorWheel):
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

    def _divider(parent, title: str) -> None:
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

    return main
