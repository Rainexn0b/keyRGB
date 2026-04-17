from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, TypeAlias

from PIL import Image

from src.core.resources.layout import KeyDef


KeyCell: TypeAlias = tuple[int, int]
KeyCells: TypeAlias = tuple[KeyCell, ...]
Keymap: TypeAlias = dict[str, KeyCells]
LayoutTweaks: TypeAlias = dict[str, float]
PerKeyLayoutTweaks: TypeAlias = dict[str, dict[str, float]]
LayoutSlotOverrides: TypeAlias = dict[str, dict[str, object]]


class _CalibratorConfigLike(Protocol):
    physical_layout: str | None
    layout_legend_pack: str | None


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> object: ...


class _PreviewLike(Protocol):
    def restore(self) -> None: ...

    def apply_probe_cell(self, row: int, col: int) -> None: ...


class _ProbeLike(Protocol):
    current_cell: KeyCell
    selected_key_id: str | None
    selected_slot_id: str | None

    def prev_cell(self) -> KeyCell: ...

    def next_cell(self) -> KeyCell: ...

    def clear_selection(self) -> None: ...


class _DeckRenderCacheLike(Protocol):
    def clear(self) -> None: ...


class _BoolVarLike(Protocol):
    def get(self) -> bool: ...


class _CalibratorAppLike(Protocol):
    profile_name: str
    cfg: _CalibratorConfigLike | None
    keymap: Keymap
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    layout_slot_overrides: LayoutSlotOverrides
    preview: _PreviewLike
    probe: _ProbeLike
    lbl_status: _ConfigurableWidget
    lbl_cell: _ConfigurableWidget
    canvas: object
    _deck_pil: Image.Image | None
    _deck_tk: object | None
    _deck_render_cache: _DeckRenderCacheLike
    _transform: object | None
    _show_backdrop_var: _BoolVarLike

    def _redraw(self) -> None: ...

    def _apply_current_probe(self) -> None: ...

    def _next(self) -> None: ...

    def _restore_original_config(self) -> None: ...

    def _save(self) -> None: ...

    def after(self, delay_ms: int, callback: Callable[[], None]) -> object: ...

    def destroy(self) -> None: ...


class _SaveKeymapStorageFn(Protocol):
    def __call__(
        self,
        profile_name: str,
        keymap: Keymap,
        *,
        physical_layout: str | None = None,
    ) -> None: ...


class _ProfilesLike(Protocol):
    def normalize_keymap(self, keymap: Mapping[str, object], *, physical_layout: str) -> Mapping[str, object]: ...


class _SanitizeKeymapCellsFn(Protocol):
    def __call__(self, keymap: Mapping[str, object], *, num_rows: int, num_cols: int) -> Keymap: ...


class _LoadKeymapFn(Protocol):
    def __call__(self, profile_name: str, *, physical_layout: str | None = None) -> Mapping[str, object]: ...


class _LoadLayoutGlobalFn(Protocol):
    def __call__(self, profile_name: str, *, physical_layout: str | None = None) -> LayoutTweaks: ...


class _LoadLayoutPerKeyFn(Protocol):
    def __call__(self, profile_name: str, *, physical_layout: str | None = None) -> PerKeyLayoutTweaks: ...


class _LoadLayoutSlotsFn(Protocol):
    def __call__(self, profile_name: str, physical_layout: str) -> LayoutSlotOverrides: ...


class _LoadLayoutLegendPackFn(Protocol):
    def __call__(self, pack_id: str) -> Mapping[str, object]: ...


class _GetLayoutKeysFn(Protocol):
    def __call__(
        self,
        physical_layout: str,
        *,
        legend_pack_id: str | None = None,
        slot_overrides: LayoutSlotOverrides | None = None,
    ) -> Iterable[KeyDef]: ...


class _SelectedLayoutLegendPackFn(Protocol):
    def __call__(self, cfg: _CalibratorConfigLike | None, *, physical_layout: str) -> str | None: ...


class _VisibleLayoutKeysFn(Protocol):
    def __call__(self, app: _CalibratorAppLike) -> list[KeyDef]: ...


class _VisibleKeyForSlotIdFn(Protocol):
    def __call__(self, app: _CalibratorAppLike, slot_id: str | None) -> KeyDef | None: ...


class _ProbeSelectedIdentityFn(Protocol):
    def __call__(self, app: _CalibratorAppLike) -> str | None: ...


ActiveProfileNameGetter: TypeAlias = Callable[[], str]
KeymapPathResolver: TypeAlias = Callable[[str], Path]
ResolveLayoutIdFn: TypeAlias = Callable[[str], str]
PhysicalLayoutIdFn: TypeAlias = Callable[[_CalibratorAppLike], str]


def keymap_path_for_active_profile(
    *,
    get_active_profile_name: ActiveProfileNameGetter,
    keymap_path: KeymapPathResolver,
) -> Path:
    return keymap_path(get_active_profile_name())


def save_keymap_for_active_profile(
    keymap: Keymap,
    *,
    physical_layout: str | None,
    get_active_profile_name: ActiveProfileNameGetter,
    save_keymap: _SaveKeymapStorageFn,
) -> None:
    save_keymap(get_active_profile_name(), keymap, physical_layout=physical_layout)


def parse_default_keymap(
    layout_id: str,
    *,
    profiles: _ProfilesLike,
    get_default_keymap: Callable[[str], Mapping[str, object]],
    sanitize_keymap_cells: _SanitizeKeymapCellsFn,
    num_rows: int,
    num_cols: int,
) -> Keymap:
    return sanitize_keymap_cells(
        profiles.normalize_keymap(get_default_keymap(layout_id), physical_layout=layout_id),
        num_rows=num_rows,
        num_cols=num_cols,
    )


def resolved_layout_label(
    layout_id: str,
    *,
    resolve_layout_id: ResolveLayoutIdFn,
    layout_labels: Mapping[str, str],
) -> str:
    resolved_layout = resolve_layout_id(layout_id)
    return layout_labels.get(resolved_layout, resolved_layout.upper())


def load_profile_state(
    profile_name: str,
    *,
    physical_layout: str,
    load_keymap: _LoadKeymapFn,
    load_layout_global: _LoadLayoutGlobalFn,
    load_layout_per_key: _LoadLayoutPerKeyFn,
    load_layout_slots: _LoadLayoutSlotsFn,
    sanitize_keymap_cells: _SanitizeKeymapCellsFn,
    num_rows: int,
    num_cols: int,
) -> tuple[Keymap, LayoutTweaks, PerKeyLayoutTweaks, LayoutSlotOverrides]:
    keymap = sanitize_keymap_cells(
        load_keymap(profile_name, physical_layout=physical_layout),
        num_rows=num_rows,
        num_cols=num_cols,
    )
    layout_tweaks = load_layout_global(profile_name, physical_layout=physical_layout)
    per_key_layout_tweaks = load_layout_per_key(profile_name, physical_layout=physical_layout)
    layout_slot_overrides = load_layout_slots(profile_name, physical_layout)
    return keymap, layout_tweaks, per_key_layout_tweaks, layout_slot_overrides


def selected_layout_legend_pack(
    cfg: _CalibratorConfigLike | None,
    *,
    physical_layout: str,
    load_layout_legend_pack: _LoadLayoutLegendPackFn,
) -> str | None:
    if cfg is None:
        return None

    requested = str(cfg.layout_legend_pack or "auto").strip().lower()
    if not requested or requested == "auto":
        return None

    pack = load_layout_legend_pack(requested)
    if not pack:
        return None

    resolved_pack_layout = str(pack.get("layout_id") or physical_layout).strip().lower()
    return requested if resolved_pack_layout == str(physical_layout or "auto").strip().lower() else None


def physical_layout_id(app: _CalibratorAppLike) -> str:
    cfg = app.cfg
    return str(cfg.physical_layout or "auto") if cfg is not None else "auto"


def visible_layout_keys(
    app: _CalibratorAppLike,
    *,
    get_layout_keys: _GetLayoutKeysFn,
    selected_layout_legend_pack_fn: _SelectedLayoutLegendPackFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
) -> list[KeyDef]:
    physical_layout = physical_layout_id_fn(app)
    return list(
        get_layout_keys(
            physical_layout,
            legend_pack_id=selected_layout_legend_pack_fn(app.cfg, physical_layout=physical_layout),
            slot_overrides=app.layout_slot_overrides,
        )
    )


def visible_key_for_slot_id(
    app: _CalibratorAppLike,
    slot_id: str | None,
    *,
    visible_layout_keys_fn: _VisibleLayoutKeysFn,
) -> KeyDef | None:
    normalized_slot_id = str(slot_id or "").strip()
    if not normalized_slot_id:
        return None

    for key in visible_layout_keys_fn(app):
        if str(key.slot_id or key.key_id) == normalized_slot_id:
            return key
    return None


def probe_selected_slot_id(app: _CalibratorAppLike, *, visible_layout_keys_fn: _VisibleLayoutKeysFn) -> str | None:
    probe = app.probe
    selected_slot_id = str(probe.selected_slot_id or "").strip()
    if selected_slot_id:
        return selected_slot_id

    selected_key_id = str(probe.selected_key_id or "").strip()
    if not selected_key_id:
        return None

    for key in visible_layout_keys_fn(app):
        if str(key.key_id) == selected_key_id:
            return str(key.slot_id or key.key_id)
    return selected_key_id


def probe_selected_key_id(
    app: _CalibratorAppLike,
    *,
    probe_selected_slot_id_fn: _ProbeSelectedIdentityFn,
    visible_key_for_slot_id_fn: _VisibleKeyForSlotIdFn,
) -> str | None:
    slot_id = probe_selected_slot_id_fn(app)
    key = visible_key_for_slot_id_fn(app, slot_id)
    if key is not None:
        return str(key.key_id)

    selected_key_id = str(app.probe.selected_key_id or "").strip()
    return selected_key_id or None
