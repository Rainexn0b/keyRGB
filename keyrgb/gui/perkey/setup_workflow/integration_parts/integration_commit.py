"""UX-04 guided setup integration: single-commit adapter (Tk-free).

Builds the :func:`finish_setup` callbacks: in-memory apply plus UI sync,
config/profile persist for the existing profile only, rollback of both
layers, and hardware apply solely via ``editor._commit(force=True)``
(``None`` in config-only mode). Only the existing profile's keymap/layout
payloads are written; colors, lightbar, and secondary payloads are never
touched here.
"""

from __future__ import annotations

import copy
from typing import cast

from ..model import SetupDraft, SetupSnapshot
from ..transaction import SetupCommitCallbacks
from .integration_types import (
    _EXPECTED_SESSION_ERRORS,
    _ProfilesModule,
    _SetupConfigProtocol,
    _SetupEditorProtocol,
    _SetupVarProtocol,
)


def _default_profiles_module() -> _ProfilesModule:
    from keyrgb.core.profile import profiles

    return profiles


def _apply_fields_to_editor(
    editor: object, fields: SetupDraft | SetupSnapshot, profiles_module: _ProfilesModule
) -> None:
    """Apply setup fields to editor memory and synchronize the visible UI."""

    typed = cast(_SetupEditorProtocol, editor)
    physical_layout = str(fields.physical_layout or "")
    if not physical_layout:
        raise ValueError("setup draft has no physical layout")
    legend_pack = str(fields.legend_pack or "auto") or "auto"
    try:
        normalized_legend = str(typed._normalize_layout_legend_pack(physical_layout, legend_pack))
    except (AttributeError, TypeError, ValueError):
        normalized_legend = legend_pack or "auto"
    try:
        normalized_slots = profiles_module.normalize_layout_slot_overrides(
            copy.deepcopy(dict(fields.slot_overrides)),
            physical_layout=physical_layout,
        )
    except (AttributeError, TypeError, ValueError):
        normalized_slots = copy.deepcopy(dict(fields.slot_overrides))
    try:
        normalized_per_key = profiles_module.normalize_layout_per_key_tweaks(
            copy.deepcopy(dict(fields.per_key_layout_tweaks)),
            physical_layout=physical_layout,
        )
    except (AttributeError, TypeError, ValueError):
        normalized_per_key = copy.deepcopy(dict(fields.per_key_layout_tweaks))

    typed._physical_layout = physical_layout
    typed._layout_legend_pack = normalized_legend
    if str(getattr(editor, "profile_name", "") or "") != str(fields.profile_name or "") and fields.profile_name:
        typed.profile_name = str(fields.profile_name)
    typed.layout_slot_overrides = dict(normalized_slots)
    typed.keymap = copy.deepcopy(dict(fields.keymap))
    typed.layout_tweaks = dict(fields.layout_tweaks)
    typed.per_key_layout_tweaks = {str(slot): dict(tweaks) for slot, tweaks in normalized_per_key.items()}

    _sync_editor_ui(editor, physical_layout, normalized_legend)


def _sync_editor_ui(editor: object, physical_layout: str, legend_pack: str) -> None:
    """Synchronize editor vars, slot controls, overlay vars, and canvas."""

    typed = cast(_SetupEditorProtocol, editor)
    try:
        layout_var: _SetupVarProtocol | None = typed._layout_var
    except AttributeError:
        layout_var = None
    if layout_var is not None:
        layout_var.set(physical_layout)
    try:
        legend_var: _SetupVarProtocol | None = typed._legend_pack_var
    except AttributeError:
        legend_var = None
    if legend_var is not None:
        legend_var.set(legend_pack)
    typed._refresh_layout_slot_controls()
    typed._sync_visible_layout_state()
    typed.overlay_controls.sync_vars_from_scope()
    typed.canvas.redraw()


def _persist_fields(
    config: _SetupConfigProtocol,
    profiles_module: _ProfilesModule,
    fields: SetupDraft | SetupSnapshot,
    profile_name: str | None,
) -> None:
    """Persist setup fields: config layout pair plus profile setup payloads.

    Only the existing profile's keymap/layout files are written; colors,
    lightbar, and secondary payloads are never touched here.
    """

    physical_layout = str(fields.physical_layout or "")
    legend_pack = str(fields.legend_pack or "auto") or "auto"
    if not physical_layout:
        raise ValueError("setup draft has no physical layout")
    name = str(profile_name or "").strip() or None
    with config.batch_update():
        config.physical_layout = physical_layout
        config.layout_legend_pack = legend_pack
    keymap = profiles_module.normalize_keymap(dict(fields.keymap), physical_layout=physical_layout)
    profiles_module.save_keymap(keymap, name, physical_layout=physical_layout)
    profiles_module.save_layout_global(dict(fields.layout_tweaks), name)
    per_key = profiles_module.normalize_layout_per_key_tweaks(
        copy.deepcopy(dict(fields.per_key_layout_tweaks)),
        physical_layout=physical_layout,
    )
    profiles_module.save_layout_per_key(per_key, name)
    slots = profiles_module.normalize_layout_slot_overrides(
        copy.deepcopy(dict(fields.slot_overrides)),
        physical_layout=physical_layout,
    )
    profiles_module.save_layout_slots(slots, name, physical_layout=physical_layout)


def _editor_profile_name(editor: object, draft: SetupDraft) -> str | None:
    name = str(draft.profile_name or getattr(editor, "profile_name", "") or "").strip()
    return name or None


def build_setup_commit_callbacks(
    editor: object,
    draft: SetupDraft,
    *,
    config_only: bool,
    profiles_module: _ProfilesModule | None = None,
) -> SetupCommitCallbacks:
    """Build the single-commit callbacks for :func:`finish_setup`.

    In-memory apply plus UI sync, config/profile persist for the existing
    profile only, rollback of both layers, and hardware apply solely via
    ``editor._commit(force=True)`` (``None`` in config-only mode).
    """

    profiles_mod = profiles_module if profiles_module is not None else _default_profiles_module()
    try:
        raw_config = getattr(editor, "config", None)
    except _EXPECTED_SESSION_ERRORS:
        raw_config = None
    if raw_config is None:
        raise ValueError("editor has no config")
    config = cast(_SetupConfigProtocol, raw_config)

    def apply_draft(current: SetupDraft) -> None:
        _apply_fields_to_editor(editor, current, profiles_mod)

    def persist(current: SetupDraft) -> None:
        _persist_fields(config, profiles_mod, current, _editor_profile_name(editor, current))

    def restore_original(snapshot: SetupSnapshot) -> None:
        _persist_fields(config, profiles_mod, snapshot, str(snapshot.profile_name or "").strip() or None)
        _apply_fields_to_editor(editor, snapshot, profiles_mod)

    def apply_hardware(current: SetupDraft) -> None:
        _ = current
        try:
            commit = cast(_SetupEditorProtocol, editor)._commit
        except AttributeError as exc:
            raise TypeError("editor cannot apply hardware state") from exc
        commit(force=True)

    return SetupCommitCallbacks(
        apply_draft=apply_draft,
        persist=persist,
        restore_original=restore_original,
        apply_hardware=None if config_only else apply_hardware,
    )
