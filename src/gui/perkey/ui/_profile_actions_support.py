"""Private support types and optional UI probes for profile actions."""

from __future__ import annotations

from functools import lru_cache
from logging import Logger
from tkinter import TclError
from typing import Callable, Protocol, Sequence, cast

from src.core.profile import profiles

from ..hardware import NUM_COLS, NUM_ROWS
from ..profile_management import KeyCell, KeyCells, Keymap, PerKeyColors, sanitize_keymap_cells

LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
LayoutSlotOverrides = dict[str, dict[str, object]]
LightbarOverlay = dict[str, bool | float]

_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}
_BACKDROP_UI_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, TclError)
_BACKDROP_RELOAD_ERRORS = _BACKDROP_UI_ERRORS + (OSError,)


class _ProfileNameVarProtocol(Protocol):
    def get(self) -> str: ...

    def set(self, value: object) -> None: ...


class _SettableProtocol(Protocol):
    def set(self, value: object) -> None: ...


class _ProfilesComboProtocol(Protocol):
    def configure(self, *, values: Sequence[str]) -> None: ...


class _OverlayControlsProtocol(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _LightbarControlsProtocol(Protocol):
    def sync_vars_from_editor(self) -> None: ...


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _BackdropModeVarOwner(Protocol):
    _backdrop_mode_var: _SettableProtocol


class _BackdropModeComboOwner(Protocol):
    _backdrop_mode_combo: _SettableProtocol


class _BackdropTransparencyOwner(Protocol):
    backdrop_transparency: _SettableProtocol


class _BackdropReloadCanvasProtocol(Protocol):
    def reload_backdrop_image(self) -> None: ...


class _RefreshLayoutSlotControlsOwner(Protocol):
    def _refresh_layout_slot_controls(self) -> None: ...


class _SelectSlotIdOwner(Protocol):
    def select_slot_id(self, slot_id: str) -> None: ...


class _PerKeyProfileEditorProtocol(Protocol):
    root: object
    config: object
    colors: PerKeyColors
    keymap: Keymap
    _physical_layout: str
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    layout_slot_overrides: LayoutSlotOverrides
    profile_name: str
    selected_key_id: str | None
    selected_slot_id: str | None
    selected_cells: KeyCells
    selected_cell: KeyCell | None
    overlay_controls: _OverlayControlsProtocol
    lightbar_controls: _LightbarControlsProtocol | None
    lightbar_overlay: LightbarOverlay
    canvas: _CanvasProtocol
    _profile_name_var: _ProfileNameVarProtocol
    _profiles_combo: _ProfilesComboProtocol

    def _slot_id_for_key_id(self, key_id: str | None) -> str | None: ...

    def _key_id_for_slot_id(self, slot_id: str) -> str | None: ...

    def _commit(self, *, force: bool = False) -> None: ...


@lru_cache(maxsize=1)
def _layout_labels() -> dict[str, str]:
    from src.core.resources.layouts import LAYOUT_CATALOG

    return {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}


def _parse_default_keymap(layout_id: str, load_default_keymap: Callable[[str], object]) -> Keymap:
    return sanitize_keymap_cells(
        profiles.normalize_keymap(load_default_keymap(layout_id), physical_layout=layout_id),
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )


def _sync_backdrop_ui_after_activation(
    editor: _PerKeyProfileEditorProtocol,
    profile_name: str,
    *,
    logger: Logger,
) -> None:
    backdrop_mode_var = _backdrop_mode_var_or_none(editor)
    if backdrop_mode_var is not None:
        backdrop_mode = profiles.load_backdrop_mode(profile_name)
        try:
            backdrop_mode_var.set(backdrop_mode)
            mode_combo = _backdrop_mode_combo_or_none(editor)
            if mode_combo is not None:
                mode_combo.set(_BACKDROP_MODE_LABELS.get(backdrop_mode, "Built-in seed"))
        except _BACKDROP_UI_ERRORS:
            logger.warning("Failed to update per-profile backdrop mode UI during activation", exc_info=True)

    backdrop_transparency = _backdrop_transparency_var_or_none(editor)
    if backdrop_transparency is not None:
        try:
            backdrop_transparency.set(float(profiles.load_backdrop_transparency(profile_name)))
        except _BACKDROP_UI_ERRORS:
            logger.warning("Failed to update per-profile backdrop transparency UI during activation", exc_info=True)

    reload_backdrop_image = _reload_backdrop_image_or_none(editor.canvas)
    if reload_backdrop_image is not None:
        try:
            reload_backdrop_image()
        except _BACKDROP_RELOAD_ERRORS:
            logger.exception("Failed to reload per-profile backdrop image during activation")


def _backdrop_mode_var_or_none(editor: object) -> _SettableProtocol | None:
    try:
        return cast(_BackdropModeVarOwner, editor)._backdrop_mode_var
    except AttributeError:
        return None


def _backdrop_mode_combo_or_none(editor: object) -> _SettableProtocol | None:
    try:
        return cast(_BackdropModeComboOwner, editor)._backdrop_mode_combo
    except AttributeError:
        return None


def _backdrop_transparency_var_or_none(editor: object) -> _SettableProtocol | None:
    try:
        return cast(_BackdropTransparencyOwner, editor).backdrop_transparency
    except AttributeError:
        return None


def _refresh_layout_slot_controls_if_present(editor: object) -> None:
    try:
        refresh_controls = cast(_RefreshLayoutSlotControlsOwner, editor)._refresh_layout_slot_controls
    except AttributeError:
        return
    refresh_controls()


def _reload_backdrop_image_or_none(canvas: object) -> Callable[[], None] | None:
    try:
        return cast(_BackdropReloadCanvasProtocol, canvas).reload_backdrop_image
    except AttributeError:
        return None


def _select_slot_id_if_present(editor: object, slot_id: str) -> bool:
    try:
        select_slot_id = cast(_SelectSlotIdOwner, editor).select_slot_id
    except AttributeError:
        return False
    select_slot_id(slot_id)
    return True
