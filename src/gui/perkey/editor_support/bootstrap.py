from __future__ import annotations

from typing import Any

from .. import window_geometry


def initialize_editor(
    app: Any,
    *,
    tk: Any,
    ttk: Any,
    config_cls: Any,
    profiles: Any,
    apply_keyrgb_window_icon: Any,
    apply_perkey_editor_geometry: Any,
    apply_clam_theme: Any,
    tk_call_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Any,
    normalize_layout_legend_pack_fn: Any,
    initial_last_non_black_color: Any,
    load_profile_colors: Any,
    sanitize_keymap_cells: Any,
    per_key_commit_pipeline_cls: Any,
    get_keyboard: Any,
    build_ui_fn: Any,
    set_status: Any,
    no_keymap_found_initial: Any,
    num_rows: int,
    num_cols: int,
) -> None:
    app._key_size = 28
    app._key_gap = 2
    app._key_margin = 8
    app._wheel_size = 240
    app._right_panel_width = max(320, app._wheel_size + 128)
    app._resize_job = None

    app.root = tk.Tk()
    app.root.title("KeyRGB - Per-key Colors")
    apply_keyrgb_window_icon(app.root)
    app.root.update_idletasks()

    min_content_width, min_content_height = window_geometry.compute_perkey_editor_min_content_size(
        num_rows=num_rows,
        num_cols=num_cols,
        key_margin=app._key_margin,
        key_size=app._key_size,
        key_gap=app._key_gap,
        right_panel_width=app._right_panel_width,
        wheel_size=app._wheel_size,
    )

    apply_perkey_editor_geometry(
        app.root,
        num_rows=num_rows,
        num_cols=num_cols,
        key_margin=app._key_margin,
        key_size=app._key_size,
        key_gap=app._key_gap,
        right_panel_width=app._right_panel_width,
        wheel_size=app._wheel_size,
    )

    style = ttk.Style()
    app.bg_color, app.fg_color = apply_clam_theme(app.root)
    style.configure("TCheckbutton", background=app.bg_color, foreground=app.fg_color)
    style.configure("TLabelframe", background=app.bg_color, foreground=app.fg_color)
    style.configure("TLabelframe.Label", background=app.bg_color, foreground=app.fg_color)
    style.configure("TRadiobutton", background=app.bg_color, foreground=app.fg_color)

    field_bg = style.lookup("TEntry", "fieldbackground") or "#3a3a3a"
    style.configure("TEntry", fieldbackground=field_bg, foreground=app.fg_color)
    style.configure("TCombobox", fieldbackground=field_bg, foreground=app.fg_color)
    try:
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", field_bg), ("disabled", field_bg)],
            foreground=[("readonly", app.fg_color), ("disabled", app.fg_color)],
        )
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.style_map",
            "Failed to apply perkey combobox style map",
            exc,
        )

    app.config = config_cls()
    app.profile_name = profiles.get_active_profile()
    app._physical_layout = app.config.physical_layout
    app._layout_legend_pack = normalize_layout_legend_pack_fn(
        app._physical_layout,
        app.config.layout_legend_pack,
    )
    app.has_lightbar_device = app._detect_lightbar_device()
    app.lightbar_overlay = profiles.load_lightbar_overlay(app.profile_name)

    app._layout_var = tk.StringVar(value=app._physical_layout)
    app._legend_pack_var = tk.StringVar(value=app._layout_legend_pack)

    app._backdrop_mode_var = tk.StringVar(value=profiles.load_backdrop_mode(app.profile_name))
    app.backdrop_transparency = tk.DoubleVar(value=float(profiles.load_backdrop_transparency(app.profile_name)))
    app._backdrop_transparency_save_job = None
    app._backdrop_transparency_redraw_job = None

    app._last_non_black_color = initial_last_non_black_color(app.config.color)
    app.colors = load_profile_colors(
        name=app.profile_name,
        config=app.config,
        current_colors={},
        num_rows=num_rows,
        num_cols=num_cols,
    )

    app.keymap = app._load_keymap()
    app.layout_tweaks = app._load_layout_tweaks()
    app.per_key_layout_tweaks = app._load_per_key_layout_tweaks()
    app.layout_slot_overrides = app._load_layout_slot_overrides()

    app.overlay_scope = tk.StringVar(value="global")
    app.apply_all_keys = tk.BooleanVar(value=False)
    app.sample_tool_enabled = tk.BooleanVar(value=False)
    app._sample_tool_has_sampled = False
    app._setup_panel_mode = None
    app._profile_name_var = tk.StringVar(value=app.profile_name)
    app.selected_key_id = None
    app.selected_slot_id = None
    app.selected_cells = ()
    app.selected_cell = None

    app._commit_pipeline = per_key_commit_pipeline_cls(commit_interval_s=0.06)

    app.kb = None
    app.kb = get_keyboard()

    build_ui_fn()
    window_geometry.fit_perkey_editor_geometry_to_content(
        app.root,
        min_content_width_px=min_content_width,
        min_content_height_px=min_content_height,
    )
    app.root.after(
        50,
        lambda: window_geometry.fit_perkey_editor_geometry_to_content(
            app.root,
            min_content_width_px=min_content_width,
            min_content_height_px=min_content_height,
        ),
    )
    app.canvas.redraw()

    if not app.keymap:
        set_status(app, no_keymap_found_initial())

    app.root.bind("<FocusIn>", lambda _event: app._reload_keymap())

    for key_def in app._get_visible_layout_keys():
        if key_def.key_id in app.keymap:
            app.select_slot_id(str(key_def.slot_id or key_def.key_id))
            break
