from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping, Protocol

from src.core.resources.layout import KeyDef

from . import _app_profile_layout


Keymap = _app_profile_layout.Keymap
LayoutTweaks = _app_profile_layout.LayoutTweaks
PerKeyLayoutTweaks = _app_profile_layout.PerKeyLayoutTweaks
LayoutSlotOverrides = _app_profile_layout.LayoutSlotOverrides
_CalibratorConfigLike = _app_profile_layout._CalibratorConfigLike
_CalibratorAppLike = _app_profile_layout._CalibratorAppLike


class _ProfileManagementLike(Protocol):
    sanitize_keymap_cells: _app_profile_layout._SanitizeKeymapCellsFn


class _LayoutCatalogLike(Protocol):
    resolve_layout_id: _app_profile_layout.ResolveLayoutIdFn


class _LayoutLegendsLike(Protocol):
    load_layout_legend_pack: _app_profile_layout._LoadLayoutLegendPackFn


class _AppProfileLayoutDeps(Protocol):
    get_active_profile_name: _app_profile_layout.ActiveProfileNameGetter
    keymap_path: _app_profile_layout.KeymapPathResolver
    save_keymap: _app_profile_layout._SaveKeymapStorageFn
    profiles: _app_profile_layout._ProfilesLike
    get_default_keymap: Callable[[str], Mapping[str, object]]
    profile_management: _ProfileManagementLike
    load_keymap: _app_profile_layout._LoadKeymapFn
    load_layout_global: _app_profile_layout._LoadLayoutGlobalFn
    load_layout_per_key: _app_profile_layout._LoadLayoutPerKeyFn
    load_layout_slots: _app_profile_layout._LoadLayoutSlotsFn
    layout_catalog: _LayoutCatalogLike
    _LAYOUT_LABELS: Mapping[str, str]
    layout_legends: _LayoutLegendsLike
    get_layout_keys: _app_profile_layout._GetLayoutKeysFn
    MATRIX_ROWS: int
    MATRIX_COLS: int
    _selected_layout_legend_pack: _app_profile_layout._SelectedLayoutLegendPackFn
    _physical_layout_id: _app_profile_layout.PhysicalLayoutIdFn
    _visible_layout_keys: _app_profile_layout._VisibleLayoutKeysFn
    _visible_key_for_slot_id: _app_profile_layout._VisibleKeyForSlotIdFn
    _probe_selected_slot_id: _app_profile_layout._ProbeSelectedIdentityFn


def _keymap_path(deps: _AppProfileLayoutDeps) -> Path:
    return _app_profile_layout.keymap_path_for_active_profile(
        get_active_profile_name=deps.get_active_profile_name,
        keymap_path=deps.keymap_path,
    )


def _save_keymap(
    deps: _AppProfileLayoutDeps,
    keymap: Keymap,
    *,
    physical_layout: str | None = None,
) -> None:
    _app_profile_layout.save_keymap_for_active_profile(
        keymap,
        physical_layout=physical_layout,
        get_active_profile_name=deps.get_active_profile_name,
        save_keymap=deps.save_keymap,
    )


def _parse_default_keymap(deps: _AppProfileLayoutDeps, layout_id: str) -> Keymap:
    return _app_profile_layout.parse_default_keymap(
        layout_id,
        profiles=deps.profiles,
        get_default_keymap=deps.get_default_keymap,
        sanitize_keymap_cells=deps.profile_management.sanitize_keymap_cells,
        num_rows=deps.MATRIX_ROWS,
        num_cols=deps.MATRIX_COLS,
    )


def _resolved_layout_label(deps: _AppProfileLayoutDeps, layout_id: str) -> str:
    return _app_profile_layout.resolved_layout_label(
        layout_id,
        resolve_layout_id=deps.layout_catalog.resolve_layout_id,
        layout_labels=deps._LAYOUT_LABELS,
    )


def _load_profile_state(
    deps: _AppProfileLayoutDeps,
    profile_name: str,
    *,
    physical_layout: str,
) -> tuple[Keymap, LayoutTweaks, PerKeyLayoutTweaks, LayoutSlotOverrides]:
    return _app_profile_layout.load_profile_state(
        profile_name,
        physical_layout=physical_layout,
        load_keymap=deps.load_keymap,
        load_layout_global=deps.load_layout_global,
        load_layout_per_key=deps.load_layout_per_key,
        load_layout_slots=deps.load_layout_slots,
        sanitize_keymap_cells=deps.profile_management.sanitize_keymap_cells,
        num_rows=deps.MATRIX_ROWS,
        num_cols=deps.MATRIX_COLS,
    )


def _selected_layout_legend_pack(
    deps: _AppProfileLayoutDeps,
    cfg: _CalibratorConfigLike | None,
    *,
    physical_layout: str,
) -> str | None:
    return _app_profile_layout.selected_layout_legend_pack(
        cfg,
        physical_layout=physical_layout,
        load_layout_legend_pack=deps.layout_legends.load_layout_legend_pack,
    )


def _physical_layout_id(_deps: _AppProfileLayoutDeps, app: _CalibratorAppLike) -> str:
    return _app_profile_layout.physical_layout_id(app)


def _visible_layout_keys(deps: _AppProfileLayoutDeps, app: _CalibratorAppLike) -> list[KeyDef]:
    return _app_profile_layout.visible_layout_keys(
        app,
        get_layout_keys=deps.get_layout_keys,
        selected_layout_legend_pack_fn=deps._selected_layout_legend_pack,
        physical_layout_id_fn=deps._physical_layout_id,
    )


def _visible_key_for_slot_id(
    deps: _AppProfileLayoutDeps,
    app: _CalibratorAppLike,
    slot_id: str | None,
) -> KeyDef | None:
    return _app_profile_layout.visible_key_for_slot_id(
        app,
        slot_id,
        visible_layout_keys_fn=deps._visible_layout_keys,
    )


def _probe_selected_slot_id(deps: _AppProfileLayoutDeps, app: _CalibratorAppLike) -> str | None:
    return _app_profile_layout.probe_selected_slot_id(
        app,
        visible_layout_keys_fn=deps._visible_layout_keys,
    )


def _probe_selected_key_id(deps: _AppProfileLayoutDeps, app: _CalibratorAppLike) -> str | None:
    return _app_profile_layout.probe_selected_key_id(
        app,
        probe_selected_slot_id_fn=deps._probe_selected_slot_id,
        visible_key_for_slot_id_fn=deps._visible_key_for_slot_id,
    )
