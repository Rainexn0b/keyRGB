"""Unit coverage for per-key editor_support.actions dispatch facades."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keyrgb.gui.perkey import (
    color_utils as color_utils_mod,
    keyboard_apply as keyboard_apply_mod,
    overlay as overlay_mod,
    profile_management as profile_management_mod,
    ui as ui_pkg,
)
from keyrgb.gui.perkey.editor_support import actions, runtime as runtime_mod
from keyrgb.gui.perkey.ui import (
    _profile_actions_ui as profile_actions_ui_mod,
    backdrop as backdrop_mod,
    bulk_color as bulk_color_mod,
    calibrator as calibrator_mod,
    full_map as full_map_mod,
    keymap as keymap_mod,
    profile_actions as profile_actions_mod,
    status as status_mod,
    wheel_apply as wheel_apply_mod,
)


def test_actions_delegate_status_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    set_status = MagicMock()
    no_map = MagicMock(return_value="no-map")
    monkeypatch.setattr(status_mod, "set_status", set_status)
    monkeypatch.setattr(status_mod, "no_keymap_found_initial", no_map)

    editor = object()
    actions.set_status(editor, "hello")
    set_status.assert_called_once_with(editor, "hello")
    assert actions.no_keymap_found_initial() == "no-map"


def test_actions_delegate_runtime_layout_and_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    save_layout = MagicMock()
    reset_layout = MagicMock()
    auto_sync = MagicMock()
    commit = MagicMock()
    load_keymap = MagicMock(return_value={"esc": ((0, 0),)})
    defaults = MagicMock(return_value={"scale": 1.0})

    monkeypatch.setattr(runtime_mod, "save_layout_tweaks", save_layout)
    monkeypatch.setattr(runtime_mod, "reset_layout_tweaks", reset_layout)
    monkeypatch.setattr(runtime_mod, "auto_sync_per_key_overlays", auto_sync)
    monkeypatch.setattr(runtime_mod, "commit", commit)
    monkeypatch.setattr(runtime_mod, "load_keymap", load_keymap)
    monkeypatch.setattr("keyrgb.core.resources.defaults.get_default_layout_tweaks", defaults)

    editor = object()
    profiles = object()
    hardware = object()
    last_color = object()

    actions.save_layout_tweaks(editor, profiles=profiles)
    save_layout.assert_called_once_with(editor, profiles=profiles, status=status_mod)

    actions.reset_layout_tweaks(editor)
    reset_layout.assert_called_once_with(
        editor,
        get_default_layout_tweaks=defaults,
        status=status_mod,
    )

    actions.auto_sync_per_key_overlays(editor)
    auto_sync.assert_called_once_with(editor, overlay=overlay_mod, status=status_mod)

    actions.commit(editor, force=True, hardware=hardware, last_non_black_color_or=last_color)
    commit.assert_called_once_with(
        editor,
        force=True,
        hardware=hardware,
        color_utils=color_utils_mod,
        keyboard_apply=keyboard_apply_mod,
        status=status_mod,
        last_non_black_color_or=last_color,
    )

    assert actions.load_keymap(editor, profiles=profiles, hardware=hardware) == {"esc": ((0, 0),)}
    load_keymap.assert_called_once_with(
        editor,
        profiles=profiles,
        profile_management=profile_management_mod,
        hardware=hardware,
    )


def test_actions_delegate_ui_entrypoints(monkeypatch: pytest.MonkeyPatch) -> None:
    run_calibrator = MagicMock()
    reload_keymap = MagicMock()
    wheel_change = MagicMock()
    wheel_release = MagicMock()
    set_backdrop = MagicMock()
    reset_backdrop = MagicMock()
    fill_all = MagicMock()
    clear_all = MagicMock()
    ensure_full_map = MagicMock()
    new_profile = MagicMock()
    activate_profile = MagicMock()
    save_profile = MagicMock()
    delete_profile = MagicMock()
    set_default_profile = MagicMock()
    save_power_policy = MagicMock()
    reset_layout_defaults = MagicMock()

    monkeypatch.setattr(calibrator_mod, "run_keymap_calibrator_ui", run_calibrator)
    monkeypatch.setattr(keymap_mod, "reload_keymap_ui", reload_keymap)
    monkeypatch.setattr(wheel_apply_mod, "on_wheel_color_change_ui", wheel_change)
    monkeypatch.setattr(wheel_apply_mod, "on_wheel_color_release_ui", wheel_release)
    monkeypatch.setattr(backdrop_mod, "set_backdrop_ui", set_backdrop)
    monkeypatch.setattr(backdrop_mod, "reset_backdrop_ui", reset_backdrop)
    monkeypatch.setattr(bulk_color_mod, "fill_all_ui", fill_all)
    monkeypatch.setattr(bulk_color_mod, "clear_all_ui", clear_all)
    monkeypatch.setattr(full_map_mod, "ensure_full_map_ui", ensure_full_map)
    monkeypatch.setattr(profile_actions_ui_mod, "new_profile_ui", new_profile)
    monkeypatch.setattr(profile_actions_ui_mod, "activate_profile_ui", activate_profile)
    monkeypatch.setattr(profile_actions_ui_mod, "save_profile_ui", save_profile)
    monkeypatch.setattr(profile_actions_ui_mod, "delete_profile_ui", delete_profile)
    monkeypatch.setattr(profile_actions_ui_mod, "set_default_profile_ui", set_default_profile)
    monkeypatch.setattr(profile_actions_ui_mod, "save_power_source_profile_policy_ui", save_power_policy)
    monkeypatch.setattr(profile_actions_mod, "reset_layout_defaults_ui", reset_layout_defaults)

    # Relative imports resolve through the ui package namespace for some symbols.
    monkeypatch.setattr(ui_pkg, "calibrator", calibrator_mod)
    monkeypatch.setattr(ui_pkg, "keymap", keymap_mod)
    monkeypatch.setattr(ui_pkg, "wheel_apply", wheel_apply_mod)
    monkeypatch.setattr(ui_pkg, "backdrop", backdrop_mod)
    monkeypatch.setattr(ui_pkg, "bulk_color", bulk_color_mod)
    monkeypatch.setattr(ui_pkg, "full_map", full_map_mod)
    monkeypatch.setattr(ui_pkg, "_profile_actions_ui", profile_actions_ui_mod)
    monkeypatch.setattr(ui_pkg, "profile_actions", profile_actions_mod)

    editor = SimpleNamespace()

    actions.run_calibrator(editor)
    run_calibrator.assert_called_once_with(editor)

    actions.reload_keymap(editor)
    reload_keymap.assert_called_once_with(editor)

    actions.on_wheel_color_change(editor, 1, 2, 3, num_rows=6, num_cols=21)
    wheel_change.assert_called_once_with(editor, 1, 2, 3, num_rows=6, num_cols=21)

    actions.on_wheel_color_release(editor, 4, 5, 6, num_rows=6, num_cols=21)
    wheel_release.assert_called_once_with(editor, 4, 5, 6, num_rows=6, num_cols=21)

    actions.set_backdrop(editor)
    set_backdrop.assert_called_once_with(editor)
    actions.reset_backdrop(editor)
    reset_backdrop.assert_called_once_with(editor)

    actions.fill_all(editor, num_rows=6, num_cols=21)
    fill_all.assert_called_once_with(editor, num_rows=6, num_cols=21)
    actions.clear_all(editor, num_rows=6, num_cols=21)
    clear_all.assert_called_once_with(editor, num_rows=6, num_cols=21)

    actions.ensure_full_map(editor, num_rows=6, num_cols=21)
    ensure_full_map.assert_called_once_with(editor, num_rows=6, num_cols=21)

    actions.new_profile(editor)
    new_profile.assert_called_once_with(editor)
    actions.activate_profile(editor)
    activate_profile.assert_called_once_with(editor)
    actions.save_profile(editor)
    save_profile.assert_called_once_with(editor)
    actions.delete_profile(editor)
    delete_profile.assert_called_once_with(editor)
    actions.set_default_profile(editor)
    set_default_profile.assert_called_once_with(editor)
    actions.save_power_source_profile_policy(editor)
    save_power_policy.assert_called_once_with(editor)

    actions.reset_layout_defaults(editor)
    reset_layout_defaults.assert_called_once_with(editor)
