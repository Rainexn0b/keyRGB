from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

from src.core.backends.base import KeyboardDevice
from src.core.config import Config

from ..commit_pipeline import PerKeyCommitPipeline
from ..profile_management import KeyCells, Keymap, PerKeyColors


LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
LayoutSlotOverrides = dict[str, dict[str, object]]
LightbarOverlay = dict[str, bool | float]


class _TkVarProtocol(Protocol):
    def get(self) -> object: ...

    def set(self, value: object) -> None: ...


class _TkRootProtocol(Protocol):
    def title(self, text: str) -> None: ...

    def update_idletasks(self) -> None: ...

    def after(self, delay_ms: int, callback: Callable[..., object]) -> object: ...

    def bind(self, sequence: str, func: Callable[..., object]) -> object: ...


class _TkModuleProtocol(Protocol):
    def Tk(self) -> _TkRootProtocol: ...

    def StringVar(self, value: object = ...) -> _TkVarProtocol: ...

    def BooleanVar(self, value: object = ...) -> _TkVarProtocol: ...

    def DoubleVar(self, value: object = ...) -> _TkVarProtocol: ...


class _TtkStyleProtocol(Protocol):
    def configure(self, style_name: str, **kwargs: object) -> object: ...

    def lookup(self, style_name: str, option_name: str) -> str: ...

    def map(self, style_name: str, **kwargs: object) -> object: ...


class _TtkModuleProtocol(Protocol):
    def Style(self) -> _TtkStyleProtocol: ...


class _ProfilesProtocol(Protocol):
    def get_active_profile(self) -> str: ...

    def load_backdrop_mode(self, name: str | None = None) -> str: ...

    def load_backdrop_transparency(self, name: str | None = None) -> float: ...

    def load_lightbar_overlay(self, name: str | None = None) -> LightbarOverlay: ...


class _VisibleLayoutKeyProtocol(Protocol):
    key_id: str
    slot_id: str | None


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _PerKeyEditorBootstrapApp(Protocol):
    _key_size: int
    _key_gap: int
    _key_margin: int
    _wheel_size: int
    _right_panel_width: int
    _resize_job: object | None
    root: _TkRootProtocol
    bg_color: str
    fg_color: str
    config: Config
    profile_name: str
    _physical_layout: str
    _layout_legend_pack: str
    has_lightbar_device: bool
    lightbar_overlay: LightbarOverlay
    _layout_var: _TkVarProtocol
    _legend_pack_var: _TkVarProtocol
    _backdrop_mode_var: _TkVarProtocol
    backdrop_transparency: _TkVarProtocol
    _backdrop_transparency_save_job: object | None
    _backdrop_transparency_redraw_job: object | None
    _last_non_black_color: tuple[int, int, int]
    colors: PerKeyColors
    keymap: Keymap
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    layout_slot_overrides: LayoutSlotOverrides
    overlay_scope: _TkVarProtocol
    apply_all_keys: _TkVarProtocol
    sample_tool_enabled: _TkVarProtocol
    _sample_tool_has_sampled: bool
    _setup_panel_mode: str | None
    _profile_name_var: _TkVarProtocol
    selected_key_id: str | None
    selected_slot_id: str | None
    selected_cells: KeyCells
    selected_cell: tuple[int, int] | None
    _commit_pipeline: PerKeyCommitPipeline
    kb: KeyboardDevice | None
    canvas: _CanvasProtocol

    def _detect_lightbar_device(self) -> bool: ...

    def _load_keymap(self) -> Keymap: ...

    def _load_layout_tweaks(self) -> LayoutTweaks: ...

    def _load_per_key_layout_tweaks(self) -> PerKeyLayoutTweaks: ...

    def _load_layout_slot_overrides(self) -> LayoutSlotOverrides: ...

    def _get_visible_layout_keys(self) -> Sequence[_VisibleLayoutKeyProtocol]: ...

    def _reload_keymap(self) -> None: ...

    def select_slot_id(self, slot_id: str) -> None: ...


def initialize_editor(
    app: object,
    *,
    tk: object,
    ttk: object,
    config_cls: type[Config],
    profiles: object,
    apply_keyrgb_window_icon: Callable[[_TkRootProtocol], object],
    apply_perkey_editor_geometry: Callable[..., object],
    compute_perkey_editor_min_content_size: Callable[..., tuple[int, int]],
    fit_perkey_editor_geometry_to_content: Callable[..., object],
    apply_clam_theme: Callable[[_TkRootProtocol], tuple[str, str]],
    tk_call_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Callable[[str, str, Exception], object],
    normalize_layout_legend_pack_fn: Callable[[str, str | None], str],
    initial_last_non_black_color: Callable[[object], tuple[int, int, int]],
    load_profile_colors: Callable[..., PerKeyColors],
    sanitize_keymap_cells: Callable[..., Keymap],
    per_key_commit_pipeline_cls: type[PerKeyCommitPipeline],
    get_keyboard: Callable[[], KeyboardDevice | None],
    build_ui_fn: Callable[[], object],
    set_status: Callable[[_PerKeyEditorBootstrapApp, str], object],
    no_keymap_found_initial: Callable[[], str],
    num_rows: int,
    num_cols: int,
) -> None:
    del sanitize_keymap_cells

    editor = cast(_PerKeyEditorBootstrapApp, app)
    tk_module = cast(_TkModuleProtocol, tk)
    ttk_module = cast(_TtkModuleProtocol, ttk)
    profiles_api = cast(_ProfilesProtocol, profiles)

    editor._key_size = 28
    editor._key_gap = 2
    editor._key_margin = 8
    editor._wheel_size = 240
    editor._right_panel_width = max(320, editor._wheel_size + 128)
    editor._resize_job = None

    editor.root = tk_module.Tk()
    editor.root.title("KeyRGB - Per-key Colors")
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

    style = ttk_module.Style()
    editor.bg_color, editor.fg_color = apply_clam_theme(editor.root)
    style.configure("TCheckbutton", background=editor.bg_color, foreground=editor.fg_color)
    style.configure("TLabelframe", background=editor.bg_color, foreground=editor.fg_color)
    style.configure("TLabelframe.Label", background=editor.bg_color, foreground=editor.fg_color)
    style.configure("TRadiobutton", background=editor.bg_color, foreground=editor.fg_color)

    field_bg = style.lookup("TEntry", "fieldbackground") or "#3a3a3a"
    style.configure("TEntry", fieldbackground=field_bg, foreground=editor.fg_color)
    style.configure("TCombobox", fieldbackground=field_bg, foreground=editor.fg_color)
    try:
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", field_bg), ("disabled", field_bg)],
            foreground=[("readonly", editor.fg_color), ("disabled", editor.fg_color)],
        )
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.style_map",
            "Failed to apply perkey combobox style map",
            exc,
        )

    editor.config = config_cls()
    editor.profile_name = profiles_api.get_active_profile()
    editor._physical_layout = editor.config.physical_layout
    editor._layout_legend_pack = normalize_layout_legend_pack_fn(
        editor._physical_layout,
        editor.config.layout_legend_pack,
    )
    editor.has_lightbar_device = editor._detect_lightbar_device()
    editor.lightbar_overlay = profiles_api.load_lightbar_overlay(editor.profile_name)

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
    editor.selected_key_id = None
    editor.selected_slot_id = None
    editor.selected_cells = ()
    editor.selected_cell = None

    editor._commit_pipeline = per_key_commit_pipeline_cls(commit_interval_s=0.06)

    editor.kb = None
    editor.kb = get_keyboard()

    build_ui_fn()
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
    editor.canvas.redraw()

    if not editor.keymap:
        set_status(editor, no_keymap_found_initial())

    editor.root.bind("<FocusIn>", lambda _event: editor._reload_keymap())

    for key_def in editor._get_visible_layout_keys():
        if key_def.key_id in editor.keymap:
            editor.select_slot_id(str(key_def.slot_id or key_def.key_id))
            break
