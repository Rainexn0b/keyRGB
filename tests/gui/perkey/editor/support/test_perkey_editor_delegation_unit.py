"""Delegation coverage for PerKeyEditor thin method surface."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.gui.perkey.editor import PerKeyEditor, _last_non_black_color_or


def test_last_non_black_color_or_handles_missing_attr() -> None:
    assert _last_non_black_color_or(SimpleNamespace(_last_non_black_color=(1, 2, 3)), (9, 9, 9)) == (1, 2, 3)
    assert _last_non_black_color_or(object(), (9, 9, 9)) == (9, 9, 9)


def test_editor_action_methods_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    actions = SimpleNamespace(
        save_layout_tweaks=MagicMock(),
        reset_layout_tweaks=MagicMock(),
        auto_sync_per_key_overlays=MagicMock(),
        run_calibrator=MagicMock(),
        reload_keymap=MagicMock(),
        commit=MagicMock(),
        on_wheel_color_change=MagicMock(),
        on_wheel_color_release=MagicMock(),
        set_backdrop=MagicMock(),
        reset_backdrop=MagicMock(),
        fill_all=MagicMock(),
        ensure_full_map=MagicMock(),
        clear_all=MagicMock(),
        new_profile=MagicMock(),
        activate_profile=MagicMock(),
        save_profile=MagicMock(),
        delete_profile=MagicMock(),
        set_default_profile=MagicMock(),
        save_power_source_profile_policy=MagicMock(),
        reset_layout_defaults=MagicMock(),
        load_keymap=MagicMock(return_value={"esc": ((0, 0),)}),
    )
    monkeypatch.setattr(editor_mod, "editor_actions", actions)
    monkeypatch.setattr(editor_mod, "on_sample_tool_toggled_ui", MagicMock())
    monkeypatch.setattr(editor_mod, "on_slot_clicked_ui", MagicMock())

    editor = SimpleNamespace(overlay_controls=SimpleNamespace(sync_vars_from_scope=MagicMock()))

    PerKeyEditor.save_layout_tweaks(editor)
    actions.save_layout_tweaks.assert_called_once()
    PerKeyEditor.reset_layout_tweaks(editor)
    PerKeyEditor.auto_sync_per_key_overlays(editor)
    PerKeyEditor._run_calibrator(editor)
    PerKeyEditor._reload_keymap(editor)
    PerKeyEditor._commit(editor, force=True)
    PerKeyEditor._set_backdrop(editor)
    PerKeyEditor._reset_backdrop(editor)
    PerKeyEditor._fill_all(editor)
    PerKeyEditor._ensure_full_map(editor)
    PerKeyEditor._clear_all(editor)
    PerKeyEditor._new_profile(editor)
    PerKeyEditor._activate_profile(editor)
    PerKeyEditor._save_profile(editor)
    PerKeyEditor._delete_profile(editor)
    PerKeyEditor._set_default_profile(editor)
    PerKeyEditor._save_power_source_profile_policy(editor)
    PerKeyEditor._reset_layout_defaults(editor)
    assert PerKeyEditor._load_keymap(editor) == {"esc": ((0, 0),)}

    PerKeyEditor.sync_overlay_vars(editor)
    editor.overlay_controls.sync_vars_from_scope.assert_called_once()

    PerKeyEditor._on_sample_tool_toggled(editor)
    editor_mod.on_sample_tool_toggled_ui.assert_called_once_with(editor)

    PerKeyEditor.on_slot_clicked(editor, "slot_a")
    editor_mod.on_slot_clicked_ui.assert_called_once()


def test_color_change_routes_to_lighting_areas_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    wheel = MagicMock()
    monkeypatch.setattr(
        editor_mod, "editor_actions", SimpleNamespace(on_wheel_color_change=wheel, on_wheel_color_release=wheel)
    )

    panel = SimpleNamespace(apply_wheel_color=MagicMock(return_value=True))
    editor = SimpleNamespace(_lighting_areas_panel=panel)

    PerKeyEditor._on_color_change(editor, 1, 2, 3)
    panel.apply_wheel_color.assert_called_with((1, 2, 3), released=False)
    wheel.assert_not_called()

    panel.apply_wheel_color.return_value = False
    PerKeyEditor._on_color_release(editor, 4, 5, 6)
    wheel.assert_called()


def test_select_slot_id_selects_keyboard_area_first(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    select = MagicMock()
    monkeypatch.setattr(editor_mod.editor_selection, "select_slot_id", select)
    panel = SimpleNamespace(select_keyboard=MagicMock())
    editor = SimpleNamespace(_lighting_areas_panel=panel)

    PerKeyEditor.select_slot_id(editor, "slot_esc")
    panel.select_keyboard.assert_called_once()
    select.assert_called_once_with(editor, "slot_esc")


def test_on_close_saves_closes_hardware_and_destroys(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    closed: list[str] = []
    destroyed: list[str] = []
    released: list[str] = []
    saves: list[str] = []

    profile_var = SimpleNamespace(
        value="Other", get=lambda: profile_var.value, set=lambda v: setattr(profile_var, "value", v)
    )

    class _Kb:
        def close(self) -> None:
            closed.append("kb")

    editor = SimpleNamespace(
        profile_name="Default",
        _profile_name_var=profile_var,
        _save_profile=lambda: saves.append("save"),
        kb=_Kb(),
        root=SimpleNamespace(destroy=lambda: destroyed.append("root")),
    )
    # ensure vars() path works
    vars(editor)["_profile_name_var"] = profile_var

    monkeypatch.setattr(
        editor_mod.dirty_state,
        "confirm_destructive_action",
        lambda _e, *, action, save_fn: save_fn() or True,
    )
    monkeypatch.setattr(editor_mod.hardware, "release_hardware_control", lambda: released.append("hw"))

    PerKeyEditor._on_close(editor)
    assert saves == ["save"]
    assert closed == ["kb"]
    assert released == ["hw"]
    assert destroyed == ["root"]
    assert editor.kb is None


def test_on_close_handles_guard_failure_cancel_and_close_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    # guard raises -> early return
    monkeypatch.setattr(
        editor_mod.dirty_state,
        "confirm_destructive_action",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no")),
    )
    editor = SimpleNamespace(kb=object(), root=SimpleNamespace(destroy=MagicMock()))
    PerKeyEditor._on_close(editor)
    editor.root.destroy.assert_not_called()

    # cancelled
    monkeypatch.setattr(editor_mod.dirty_state, "confirm_destructive_action", lambda *_a, **_k: False)
    PerKeyEditor._on_close(editor)
    editor.root.destroy.assert_not_called()

    # close errors swallowed
    class _BadKb:
        def close(self) -> None:
            raise OSError("gone")

    destroyed: list[str] = []
    editor = SimpleNamespace(
        profile_name="P",
        _profile_name_var=SimpleNamespace(get=lambda: "P", set=lambda _v: None),
        _save_profile=lambda: None,
        kb=_BadKb(),
        root=SimpleNamespace(destroy=lambda: destroyed.append("ok")),
    )
    vars(editor)["_profile_name_var"] = editor._profile_name_var
    monkeypatch.setattr(editor_mod.dirty_state, "confirm_destructive_action", lambda *_a, **_k: True)
    monkeypatch.setattr(editor_mod.hardware, "release_hardware_control", lambda: None)
    PerKeyEditor._on_close(editor)
    assert destroyed == ["ok"]


def test_backdrop_and_layout_helpers_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    backdrop = SimpleNamespace(
        on_backdrop_transparency_changed=MagicMock(),
        apply_backdrop_transparency_redraw=MagicMock(),
        persist_backdrop_transparency=MagicMock(),
        on_backdrop_mode_changed=MagicMock(),
    )
    layout = SimpleNamespace(
        sync_layout_legend_pack_ui=MagicMock(),
        detect_lightbar_device=MagicMock(return_value=True),
        persist_layout_slot_overrides=MagicMock(),
        set_layout_slot_visibility=MagicMock(),
        set_layout_slot_label=MagicMock(),
    )
    monkeypatch.setattr(editor_mod, "editor_backdrop", backdrop)
    monkeypatch.setattr(editor_mod, "editor_layout", layout)
    monkeypatch.setattr(editor_mod.dirty_state, "mark_saved", MagicMock())

    editor = SimpleNamespace()
    PerKeyEditor._on_backdrop_transparency_changed(editor, "0.5")
    backdrop.on_backdrop_transparency_changed.assert_called_once()
    PerKeyEditor._apply_backdrop_transparency_redraw(editor)
    PerKeyEditor._persist_backdrop_transparency(editor)
    PerKeyEditor._on_backdrop_mode_changed(editor)
    PerKeyEditor._sync_layout_legend_pack_ui(editor)
    assert PerKeyEditor._detect_lightbar_device(editor) is True
    PerKeyEditor._persist_layout_slot_overrides(editor)
    PerKeyEditor._set_layout_slot_visibility(editor, "esc", False)
    PerKeyEditor._set_layout_slot_label(editor, "esc", "Esc")
    PerKeyEditor._mark_saved_snapshot(editor)
    editor_mod.dirty_state.mark_saved.assert_called_once_with(editor)


def test_build_ui_and_main_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.gui.perkey.editor as editor_mod

    build = MagicMock()
    monkeypatch.setitem(
        __import__("sys").modules, "src.gui.perkey.editor_support.ui", SimpleNamespace(build_editor_ui=build)
    )
    # ensure import path
    import src.gui.perkey.editor_support.ui as ui_mod

    monkeypatch.setattr(ui_mod, "build_editor_ui", build)
    PerKeyEditor._build_ui(SimpleNamespace())
    build.assert_called_once()

    launch = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "src.gui.perkey.launch", SimpleNamespace(main=launch))
    import src.gui.perkey.launch as launch_mod

    monkeypatch.setattr(launch_mod, "main", launch)
    editor_mod.main()
    launch.assert_called_once()
