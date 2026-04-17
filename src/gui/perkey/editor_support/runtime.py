from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

KeymapCells = dict[str, tuple[tuple[int, int], ...]]


class _OverlayScope(Protocol):
    def get(self) -> object: ...


class _OverlayControls(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _Canvas(Protocol):
    def redraw(self) -> None: ...


class _Config(Protocol):
    color: Sequence[int]


class _CommitPipeline(Protocol):
    def commit(
        self,
        *,
        kb: object,
        colors: dict[object, object],
        config: _Config,
        num_rows: int,
        num_cols: int,
        base_color: tuple[int, int, int],
        fallback_color: tuple[int, int, int],
        push_fn: object,
        force: bool,
    ) -> tuple[object, object]: ...


class _ProfilesModule(Protocol):
    def save_layout_per_key(self, tweaks: object, profile_name: str) -> None: ...

    def save_layout_global(self, tweaks: object, profile_name: str) -> None: ...

    def load_keymap(self, profile_name: str, *, physical_layout: str) -> object: ...


class _StatusModule(Protocol):
    def set_status(self, editor: object, message: str) -> None: ...

    def saved_overlay_tweaks_for_key(self, key_id: str) -> str: ...

    def saved_overlay_tweaks_global(self) -> str: ...

    def reset_overlay_tweaks_for_key(self, key_id: str) -> str: ...

    def reset_overlay_tweaks_global(self) -> str: ...

    def auto_synced_overlay_tweaks(self) -> str: ...

    def hardware_write_paused(self) -> str: ...


class _DefaultLayoutTweaksLoader(Protocol):
    def __call__(self, physical_layout: str) -> dict[str, float]: ...


class _OverlayModule(Protocol):
    def auto_sync_per_key_overlays(
        self,
        *,
        layout_tweaks: object,
        per_key_layout_tweaks: object,
        keys: object,
    ) -> None: ...


class _HardwareModule(Protocol):
    NUM_ROWS: int
    NUM_COLS: int


class _ColorUtilsModule(Protocol):
    def rgb_ints(self, value: object) -> tuple[int, int, int]: ...


class _KeyboardApplyModule(Protocol):
    push_per_key_colors: object


class _ProfileManagementModule(Protocol):
    def sanitize_keymap_cells(
        self,
        keymap: object,
        *,
        num_rows: int,
        num_cols: int,
    ) -> KeymapCells: ...


class _Editor(Protocol):
    overlay_scope: _OverlayScope
    selected_key_id: str | None
    profile_name: str
    layout_tweaks: dict[str, float]
    per_key_layout_tweaks: dict[str, dict[str, float]]
    _physical_layout: str
    _setup_panel_mode: str | None
    overlay_controls: _OverlayControls
    canvas: _Canvas
    config: _Config
    kb: object
    colors: object
    _commit_pipeline: _CommitPipeline

    def _selected_overlay_identity(self) -> str | None: ...

    def _get_visible_layout_keys(self) -> object: ...


def save_layout_tweaks(editor: _Editor, *, profiles: _ProfilesModule, status: _StatusModule) -> None:
    selected_identity = editor._selected_overlay_identity()
    if editor.overlay_scope.get() == "key" and selected_identity:
        profiles.save_layout_per_key(editor.per_key_layout_tweaks, editor.profile_name)
        status.set_status(editor, status.saved_overlay_tweaks_for_key(editor.selected_key_id or selected_identity))
        return

    profiles.save_layout_global(editor.layout_tweaks, editor.profile_name)
    status.set_status(editor, status.saved_overlay_tweaks_global())


def reset_layout_tweaks(
    editor: _Editor,
    *,
    get_default_layout_tweaks: _DefaultLayoutTweaksLoader,
    status: _StatusModule,
) -> None:
    selected_identity = editor._selected_overlay_identity()
    if editor.overlay_scope.get() == "key" and selected_identity:
        editor.per_key_layout_tweaks.pop(selected_identity, None)
        editor.overlay_controls.sync_vars_from_scope()
        editor.canvas.redraw()
        status.set_status(editor, status.reset_overlay_tweaks_for_key(editor.selected_key_id or selected_identity))
        return

    editor.layout_tweaks = get_default_layout_tweaks(editor._physical_layout)
    editor.overlay_controls.sync_vars_from_scope()
    editor.canvas.redraw()
    status.set_status(editor, status.reset_overlay_tweaks_global())


def auto_sync_per_key_overlays(
    editor: _Editor,
    *,
    overlay: _OverlayModule,
    status: _StatusModule,
) -> None:
    overlay.auto_sync_per_key_overlays(
        layout_tweaks=editor.layout_tweaks,
        per_key_layout_tweaks=editor.per_key_layout_tweaks,
        keys=editor._get_visible_layout_keys(),
    )

    if editor._setup_panel_mode == "overlay":
        editor.overlay_controls.sync_vars_from_scope()
    editor.canvas.redraw()
    status.set_status(editor, status.auto_synced_overlay_tweaks())


def commit(
    editor: _Editor,
    *,
    force: bool,
    hardware: _HardwareModule,
    color_utils: _ColorUtilsModule,
    keyboard_apply: _KeyboardApplyModule,
    status: _StatusModule,
    last_non_black_color_or: Callable[[object, object], object],
) -> None:
    prev_kb = editor.kb
    fallback = tuple(editor.config.color)
    base = tuple(last_non_black_color_or(editor, fallback))
    editor.kb, editor.colors = editor._commit_pipeline.commit(
        kb=editor.kb,
        colors=dict(editor.colors),
        config=editor.config,
        num_rows=hardware.NUM_ROWS,
        num_cols=hardware.NUM_COLS,
        base_color=color_utils.rgb_ints(base),
        fallback_color=color_utils.rgb_ints(fallback),
        push_fn=keyboard_apply.push_per_key_colors,
        force=bool(force),
    )

    if prev_kb is not None and editor.kb is None:
        status.set_status(editor, status.hardware_write_paused())


def load_keymap(
    editor: _Editor,
    *,
    profiles: _ProfilesModule,
    profile_management: _ProfileManagementModule,
    hardware: _HardwareModule,
) -> KeymapCells:
    return profile_management.sanitize_keymap_cells(
        profiles.load_keymap(editor.profile_name, physical_layout=editor._physical_layout),
        num_rows=hardware.NUM_ROWS,
        num_cols=hardware.NUM_COLS,
    )
