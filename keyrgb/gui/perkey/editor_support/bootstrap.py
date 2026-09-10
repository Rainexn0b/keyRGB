from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from keyrgb.core.backends.base import KeyboardDevice
from keyrgb.core.config import Config
from keyrgb.gui.utils.window_bindings import install_window_bindings
from keyrgb.gui.utils.window_state import WindowGeometryTracker

from ..commit_pipeline import PerKeyCommitPipeline
from ..profile_management import PerKeyColors
from . import bootstrap_protocols as _protocols, dirty_state

PERKEY_WINDOW_ID = "perkey"
PERKEY_SCREEN_RATIO_CAP = 0.92

logger = logging.getLogger(__name__)

LayoutTweaks = _protocols.LayoutTweaks
PerKeyLayoutTweaks = _protocols.PerKeyLayoutTweaks
LayoutSlotOverrides = _protocols.LayoutSlotOverrides
LightbarOverlay = _protocols.LightbarOverlay
_TkVarProtocol = _protocols._TkVarProtocol
_TkRootProtocol = _protocols._TkRootProtocol
_TkModuleProtocol = _protocols._TkModuleProtocol
_ProfilesProtocol = _protocols._ProfilesProtocol
_VisibleLayoutKeyProtocol = _protocols._VisibleLayoutKeyProtocol
_CanvasProtocol = _protocols._CanvasProtocol
_PerKeyEditorBootstrapApp = _protocols._PerKeyEditorBootstrapApp


def initialize_editor(
    app: object,
    *,
    tk: object,
    config_cls: type[Config],
    profiles: object,
    apply_keyrgb_window_icon: Callable[[_TkRootProtocol], object],
    apply_perkey_editor_geometry: Callable[..., object],
    compute_perkey_editor_min_content_size: Callable[..., tuple[int, int]],
    fit_perkey_editor_geometry_to_content: Callable[..., object],
    apply_clam_theme: Callable[..., tuple[str, str]],
    normalize_layout_legend_pack_fn: Callable[[str, str | None], str],
    initial_last_non_black_color: Callable[[object], tuple[int, int, int]],
    load_profile_colors: Callable[..., PerKeyColors],
    per_key_commit_pipeline_cls: type[PerKeyCommitPipeline],
    get_keyboard: Callable[[], KeyboardDevice | None],
    build_ui_fn: Callable[[], object],
    set_status: Callable[[_PerKeyEditorBootstrapApp, str], object],
    no_keymap_found_initial: Callable[[], str],
    num_rows: int,
    num_cols: int,
) -> None:
    editor = cast(_PerKeyEditorBootstrapApp, app)
    tk_module = cast(_TkModuleProtocol, tk)
    profiles_api = cast(_ProfilesProtocol, profiles)

    editor._key_size = 28
    editor._key_gap = 2
    editor._key_margin = 8
    editor._wheel_size = 240
    editor._right_panel_width = max(320, editor._wheel_size + 128)
    editor._resize_job = None

    editor.root = tk_module.Tk()
    editor.root.title("KeyRGB - Lighting Profile Editor")
    apply_keyrgb_window_icon(editor.root)
    editor.root.update_idletasks()

    min_content_width, min_content_height = compute_perkey_editor_min_content_size(
        num_rows=num_rows,
        num_cols=num_cols,
        key_margin=editor._key_margin,
        key_size=editor._key_size,
        key_gap=editor._key_gap,
        right_panel_width=editor._right_panel_width,
        wheel_size=editor._wheel_size,
    )

    geometry_tracker = WindowGeometryTracker(
        editor.root,
        PERKEY_WINDOW_ID,
        min_content_width,
        min_content_height,
        screen_ratio_cap=PERKEY_SCREEN_RATIO_CAP,
    )
    vars(editor)["_window_geometry_tracker"] = geometry_tracker
    restored_geometry = bool(geometry_tracker.restore())
    if not restored_geometry:
        apply_perkey_editor_geometry(
            editor.root,
            num_rows=num_rows,
            num_cols=num_cols,
            key_margin=editor._key_margin,
            key_size=editor._key_size,
            key_gap=editor._key_gap,
            right_panel_width=editor._right_panel_width,
            wheel_size=editor._wheel_size,
        )

    # Widget styling (frames, labelframes, radios, entries, comboboxes,
    # checkbuttons, and focus/disabled maps) is owned centrally by
    # keyrgb.gui.theme.ttk via apply_clam_theme; no per-window overrides here.
    editor.bg_color, editor.fg_color = apply_clam_theme(editor.root)

    editor.config = config_cls()
    editor.profile_name = profiles_api.get_active_profile()
    editor._physical_layout = editor.config.physical_layout
    editor._layout_legend_pack = normalize_layout_legend_pack_fn(
        editor._physical_layout,
        editor.config.layout_legend_pack,
    )
    editor.has_lightbar_device = editor._detect_lightbar_device()
    editor.lightbar_overlay = profiles_api.load_lightbar_overlay(editor.profile_name)
    load_secondary_lighting = getattr(profiles_api, "load_secondary_lighting", None)
    editor.secondary_lighting = (
        cast(Callable[[str], dict[str, object] | None], load_secondary_lighting)(editor.profile_name)
        if callable(load_secondary_lighting)
        else None
    )

    editor._layout_var = tk_module.StringVar(value=editor._physical_layout)
    editor._legend_pack_var = tk_module.StringVar(value=editor._layout_legend_pack)

    editor._backdrop_mode_var = tk_module.StringVar(value=profiles_api.load_backdrop_mode(editor.profile_name))
    editor.backdrop_transparency = tk_module.DoubleVar(
        value=float(profiles_api.load_backdrop_transparency(editor.profile_name))
    )
    editor._backdrop_transparency_save_job = None
    editor._backdrop_transparency_redraw_job = None

    editor._last_non_black_color = initial_last_non_black_color(editor.config.color)
    editor.colors = load_profile_colors(
        name=editor.profile_name,
        config=editor.config,
        current_colors={},
        num_rows=num_rows,
        num_cols=num_cols,
    )

    editor.keymap = editor._load_keymap()
    editor.layout_tweaks = editor._load_layout_tweaks()
    editor.per_key_layout_tweaks = editor._load_per_key_layout_tweaks()
    editor.layout_slot_overrides = editor._load_layout_slot_overrides()

    editor.overlay_scope = tk_module.StringVar(value="global")
    editor.apply_all_keys = tk_module.BooleanVar(value=False)
    editor.sample_tool_enabled = tk_module.BooleanVar(value=False)
    editor._sample_tool_has_sampled = False
    editor._setup_panel_mode = None
    editor._profile_name_var = tk_module.StringVar(value=editor.profile_name)
    editor._ac_power_source_profile_var = tk_module.StringVar(
        value=str(editor.config.ac_perkey_profile_name or "").strip() or "Keep current profile"
    )
    editor._battery_power_source_profile_var = tk_module.StringVar(
        value=str(editor.config.battery_perkey_profile_name or "").strip() or "Keep current profile"
    )
    editor.selected_key_id = None
    editor.selected_slot_id = None
    editor.selected_cells = ()
    editor.selected_cell = None

    editor._commit_pipeline = per_key_commit_pipeline_cls(commit_interval_s=0.06)

    editor.kb = None
    editor.kb = get_keyboard()

    build_ui_fn()
    protocol = getattr(editor.root, "protocol", None)
    if callable(protocol):
        protocol("WM_DELETE_WINDOW", editor._on_close)
    # UX-08 shared shortcuts: Ctrl+W closes (via dirty-checked _on_close),
    # Ctrl+S saves. Escape is intentionally not bound here so combobox and
    # entry editing keep native cancel behavior. Initial focus stays owned
    # by build_editor_ui (UX-05 backdrop selector).
    install_window_bindings(
        editor.root,
        on_close=editor._on_close,
        on_save=editor._save_profile,
        close_on_escape=False,
    )
    dirty_state.mark_saved(editor)
    if restored_geometry:
        # Theme/font layout can require more space than the pre-widget grid
        # estimate. Grow the resize floor after UI construction without
        # recentering or shrinking the restored window.
        try:
            editor.root.update_idletasks()
            screen_w = int(editor.root.winfo_screenwidth())
            screen_h = int(editor.root.winfo_screenheight())
            requested_width = max(int(min_content_width), int(editor.root.winfo_reqwidth()))
            requested_height = max(int(min_content_height), int(editor.root.winfo_reqheight()))
            editor.root.minsize(
                min(requested_width, int(screen_w * PERKEY_SCREEN_RATIO_CAP)),
                min(requested_height, int(screen_h * PERKEY_SCREEN_RATIO_CAP)),
            )
        except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: Tk/WM boundary is duck-typed here so TclError cannot be named; the restored size is kept when the floor cannot be re-asserted
            logger.debug("Per-key editor keeps restored geometry without a resize floor: %s", exc)
    else:
        fit_perkey_editor_geometry_to_content(
            editor.root,
            min_content_width_px=min_content_width,
            min_content_height_px=min_content_height,
        )
        editor.root.after(
            50,
            lambda: fit_perkey_editor_geometry_to_content(
                editor.root,
                min_content_width_px=min_content_width,
                min_content_height_px=min_content_height,
            ),
        )
    editor.root.after(60, geometry_tracker.start_tracking)
    editor.canvas.redraw()

    if not editor.keymap:
        set_status(editor, no_keymap_found_initial())

    for key_def in editor._get_visible_layout_keys():
        if key_def.key_id in editor.keymap:
            editor.select_slot_id(str(key_def.slot_id or key_def.key_id))
            break
