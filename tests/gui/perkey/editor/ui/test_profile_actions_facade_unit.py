"""Coverage for profile_actions facades and reset_layout_defaults_ui."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.gui.perkey.ui.profile_actions as actions


def test_lazy_import_facades_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    # Call wrappers so deferred imports execute.
    assert callable(actions.get_default_keymap)
    assert callable(actions.get_default_layout_tweaks)
    assert callable(actions.get_default_per_key_tweaks)
    assert callable(actions.get_layout_keys)
    assert callable(actions.resolve_layout_id)
    assert callable(actions.ensure_full_map_ui)
    assert callable(actions.select_visible_identity)
    assert callable(actions.active_profile)
    assert callable(actions.default_profile_set)
    assert callable(actions.layout_defaults_reset)
    assert callable(actions.saved_profile)
    assert callable(actions.set_status)
    assert callable(actions.activate_profile)
    assert callable(actions.delete_profile)
    assert callable(actions.keymap_cells_for)
    assert callable(actions.primary_cell)
    assert callable(actions.sanitize_keymap_cells)
    assert callable(actions.save_profile)
    assert callable(actions.read_on_ac_power)

    # Smoke-call a few that are pure enough with real modules
    assert isinstance(actions.layout_defaults_reset("ANSI"), str)
    assert isinstance(actions.active_profile("Default"), str)
    assert isinstance(actions.saved_profile("Default"), str)
    assert isinstance(actions.default_profile_set("Default"), str)


def test_save_guard_and_mark_saved_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    saves: list[str] = []
    monkeypatch.setattr(actions, "save_profile_ui", lambda _e: saves.append("save"))

    var = SimpleNamespace(value="Other", get=lambda: var.value, set=lambda v: setattr(var, "value", v))
    editor = SimpleNamespace(profile_name="Default", _profile_name_var=var)
    actions._save_current_profile_for_guard(editor)
    assert saves == ["save"]
    assert var.value == "Other"  # restored

    confirmed: list[str] = []
    monkeypatch.setattr(
        actions.dirty_state,
        "confirm_destructive_action",
        lambda _e, *, action, save_fn: confirmed.append(action) or True,
    )
    assert actions._guard_destructive_profile_action(editor, "deleting") is True
    assert confirmed == ["deleting"]

    editor2 = SimpleNamespace(_mark_saved_snapshot=MagicMock())
    actions._mark_saved_snapshot_if_supported(editor2)
    editor2._mark_saved_snapshot.assert_called_once()
    actions._mark_saved_snapshot_if_supported(object())  # AttributeError path


def test_reset_layout_defaults_ui_restores_defaults_and_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []
    monkeypatch.setattr(actions, "resolve_layout_id", lambda layout: "ansi")
    monkeypatch.setattr(actions, "get_default_keymap", lambda _layout: {"esc": "0,0", "a": "1,0"})
    monkeypatch.setattr(actions, "_parse_default_keymap", lambda layout, loader: {"esc": ((0, 0),), "a": ((1, 0),)})
    monkeypatch.setattr(actions, "get_default_layout_tweaks", lambda _layout: {"scale": 1.0})
    monkeypatch.setattr(actions, "get_default_per_key_tweaks", lambda _layout: {})
    monkeypatch.setattr(
        actions.profiles,
        "normalize_layout_per_key_tweaks",
        lambda tweaks, *, physical_layout: tweaks,
    )
    monkeypatch.setattr(
        actions.profiles,
        "save_layout_slots",
        lambda overrides, name, *, physical_layout: {},
    )
    monkeypatch.setattr(actions, "_refresh_layout_slot_controls_if_present", MagicMock())
    monkeypatch.setattr(
        actions,
        "get_layout_keys",
        lambda layout, slot_overrides=None: [
            SimpleNamespace(key_id="esc", slot_id="slot_esc"),
            SimpleNamespace(key_id="a", slot_id="slot_a"),
        ],
    )
    monkeypatch.setattr(actions, "keymap_cells_for", lambda km, key, **k: km.get(key, ()))
    monkeypatch.setattr(actions, "primary_cell", lambda cells: cells[0] if cells else None)
    monkeypatch.setattr(actions, "select_visible_identity", MagicMock())
    monkeypatch.setattr(actions, "set_status", lambda _e, msg: statuses.append(msg))
    monkeypatch.setattr(actions, "layout_defaults_reset", lambda label: f"reset:{label}")
    monkeypatch.setattr(actions, "_layout_labels", lambda: {"ansi": "ANSI"})

    editor = SimpleNamespace(
        _physical_layout="ansi",
        profile_name="Default",
        keymap={},
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={"x": {}},
        selected_key_id="esc",
        selected_slot_id=None,
        selected_cells=(),
        selected_cell=None,
        _slot_id_for_key_id=lambda kid: "slot_esc" if kid == "esc" else None,
        _key_id_for_slot_id=lambda sid: "esc" if sid == "slot_esc" else None,
        overlay_controls=SimpleNamespace(sync_vars_from_scope=MagicMock()),
        canvas=SimpleNamespace(redraw=MagicMock()),
    )

    actions.reset_layout_defaults_ui(editor)

    assert editor.keymap == {"esc": ((0, 0),), "a": ((1, 0),)}
    assert editor.layout_tweaks == {"scale": 1.0}
    assert editor.selected_slot_id == "slot_esc"
    assert editor.selected_key_id == "esc"
    assert editor.selected_cells == ((0, 0),)
    editor.overlay_controls.sync_vars_from_scope.assert_called_once()
    editor.canvas.redraw.assert_called_once()
    assert statuses == ["reset:ANSI"]


def test_reset_layout_defaults_ui_selects_first_mapped_when_selection_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(actions, "resolve_layout_id", lambda layout: "ansi")
    monkeypatch.setattr(actions, "_parse_default_keymap", lambda *_a: {"a": ((1, 0),)})
    monkeypatch.setattr(actions, "get_default_layout_tweaks", lambda _l: {})
    monkeypatch.setattr(actions, "get_default_per_key_tweaks", lambda _l: {})
    monkeypatch.setattr(actions.profiles, "normalize_layout_per_key_tweaks", lambda t, **_k: t)
    monkeypatch.setattr(actions.profiles, "save_layout_slots", lambda *_a, **_k: {})
    monkeypatch.setattr(actions, "_refresh_layout_slot_controls_if_present", lambda _e: None)
    monkeypatch.setattr(
        actions,
        "get_layout_keys",
        lambda *_a, **_k: [SimpleNamespace(key_id="a", slot_id="slot_a")],
    )
    monkeypatch.setattr(actions, "keymap_cells_for", lambda km, key, **k: km.get(str(key), ()))
    monkeypatch.setattr(actions, "primary_cell", lambda cells: None)
    select = MagicMock()
    monkeypatch.setattr(actions, "select_visible_identity", select)
    monkeypatch.setattr(actions, "set_status", lambda *_a: None)
    monkeypatch.setattr(actions, "layout_defaults_reset", lambda label: label)
    monkeypatch.setattr(actions, "_layout_labels", dict)

    editor = SimpleNamespace(
        _physical_layout="ansi",
        profile_name="Default",
        keymap={},
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        selected_key_id="gone",
        selected_slot_id="missing",
        selected_cells=((9, 9),),
        selected_cell=(9, 9),
        _slot_id_for_key_id=lambda _k: None,
        _key_id_for_slot_id=lambda _s: None,
        overlay_controls=SimpleNamespace(sync_vars_from_scope=MagicMock()),
        canvas=SimpleNamespace(redraw=MagicMock()),
    )

    actions.reset_layout_defaults_ui(editor)
    assert editor.selected_key_id is None
    select.assert_called_once()
