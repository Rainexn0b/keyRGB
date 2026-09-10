from __future__ import annotations

from keyrgb.gui.perkey.ui.responsive_columns import ResponsiveEntry, install_responsive_columns
from keyrgb.gui.theme import metrics as theme_metrics


def build_advanced_tab(editor, *, ttk, tk, OverlayControls, LightbarControls, LightingAreasPanel) -> None:
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
