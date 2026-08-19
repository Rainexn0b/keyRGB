from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import keyrgb.gui.perkey.ui._profile_actions_ui as actions_ui
import keyrgb.gui.perkey.ui.profile_actions as actions
from keyrgb.core.resources.layouts import slot_id_for_key_id
from keyrgb.gui.perkey.profile_management import ActivatedProfile, DeleteProfileResult, keymap_cells_for, primary_cell


class DummyVar:
    def __init__(self, value: str):
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class DummyLabel:
    def __init__(self):
        self.text = ""

    def config(self, *, text: str) -> None:
        self.text = text


class DummyCanvas:
    def __init__(self):
        self.redraw_calls = 0
        self.reload_backdrop_calls = 0
        self.reload_backdrop_error: Exception | None = None

    def redraw(self) -> None:
        self.redraw_calls += 1

    def reload_backdrop_image(self) -> None:
        self.reload_backdrop_calls += 1
        if self.reload_backdrop_error is not None:
            raise self.reload_backdrop_error


class DummyOverlayControls:
    def __init__(self):
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


class DummyLightbarControls:
    def __init__(self):
        self.sync_calls = 0

    def sync_vars_from_editor(self) -> None:
        self.sync_calls += 1


class DummyCombo:
    def __init__(self):
        self.values = None

    def configure(self, *, values):
        self.values = list(values)


class DummySettable:
    def __init__(self):
        self.value = None

    def set(self, value) -> None:
        self.value = value


@dataclass
class DummyEditor:
    _profile_name_var: DummyVar
    config: object
    colors: dict
    keymap: dict
    _physical_layout: str
    layout_tweaks: dict
    per_key_layout_tweaks: dict
    layout_slot_overrides: dict
    profile_name: str
    selected_key_id: str | None
    selected_slot_id: str | None
    overlay_controls: DummyOverlayControls
    lightbar_controls: DummyLightbarControls | None
    lightbar_overlay: dict
    canvas: DummyCanvas
    status_label: DummyLabel
    _profiles_combo: DummyCombo
    _ac_power_source_profile_var: DummyVar | None = None
    _battery_power_source_profile_var: DummyVar | None = None
    _ac_power_source_profile_combo: DummyCombo | None = None
    _battery_power_source_profile_combo: DummyCombo | None = None
    _activate_profile: object = None
    selected_cells: tuple[tuple[int, int], ...] = ()
    commit_calls: int = 0
    select_calls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.select_calls is None:
            self.select_calls = []

    def _commit(self, *, force: bool = False) -> None:
        self.commit_calls += 1

    def select_key_id(self, key_id: str) -> None:
        self.selected_key_id = key_id
        self.selected_cells = keymap_cells_for(self.keymap, key_id)
        self.selected_cell = primary_cell(self.selected_cells)
        self.select_calls.append(key_id)

    def select_slot_id(self, slot_id: str) -> None:
        self.selected_slot_id = str(slot_id)
        if self.selected_slot_id == str(
            slot_id_for_key_id(self._physical_layout, "nonusbackslash") or "nonusbackslash"
        ):
            self.selected_key_id = "nonusbackslash"
        elif self.selected_slot_id == str(slot_id_for_key_id(self._physical_layout, "enter") or "enter"):
            self.selected_key_id = "enter"
        elif self.selected_slot_id == "K":
            self.selected_key_id = "K"
        self.selected_cells = keymap_cells_for(self.keymap, self.selected_key_id, slot_id=self.selected_slot_id)
        self.selected_cell = primary_cell(self.selected_cells)
        self.select_calls.append(str(slot_id))

    def _slot_id_for_key_id(self, key_id: str) -> str | None:
        return str(slot_id_for_key_id(self._physical_layout, key_id) or key_id)

    def _key_id_for_slot_id(self, slot_id: str) -> str | None:
        candidates = {
            str(slot_id_for_key_id(self._physical_layout, "nonusbackslash") or "nonusbackslash"): "nonusbackslash",
            str(slot_id_for_key_id(self._physical_layout, "enter") or "enter"): "enter",
            "K": "K",
        }
        return candidates.get(str(slot_id))

    def _refresh_layout_slot_controls(self) -> None:
        return None


def test_activate_profile_ui_updates_state_and_redraws(monkeypatch) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors, num_rows, num_cols, physical_layout):
        assert num_rows > 0
        assert num_cols > 0
        assert physical_layout == "ansi"
        return ActivatedProfile(
            name="p2",
            keymap={"K": ((0, 0), (0, 1))},
            layout_tweaks={"dx": 1.0},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
            layout_slot_overrides={"nonusbackslash": {"visible": False}},
            lightbar_overlay={"visible": True, "length": 0.8},
        )

    monkeypatch.setattr(actions, "activate_profile", fake_activate_profile)
    monkeypatch.setattr(actions.profiles, "load_backdrop_mode", lambda _name: "custom")
    monkeypatch.setattr(actions.profiles, "load_backdrop_transparency", lambda _name: 42)

    full_map_calls = {"n": 0}

    def fake_ensure_full_map_ui(_editor, *, num_rows: int, num_cols: int) -> None:
        assert num_rows > 0
        assert num_cols > 0
        full_map_calls["n"] += 1

    monkeypatch.setattr(actions, "ensure_full_map_ui", fake_ensure_full_map_ui)

    ed = DummyEditor(
        _profile_name_var=DummyVar("p1"),
        config=object(),
        colors={(0, 0): (9, 9, 9)},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p1",
        selected_key_id="K",
        selected_slot_id="K",
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=DummyLightbarControls(),
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    ed._backdrop_mode_var = DummyVar("none")
    ed.backdrop_transparency = DummyVar(0.0)
    ed._backdrop_mode_combo = DummySettable()

    actions_ui.activate_profile_ui(ed)

    assert ed.profile_name == "p2"
    assert ed._profile_name_var.get() == "p2"
    assert ed.keymap == {"K": ((0, 0), (0, 1))}
    assert ed.selected_cells == ((0, 0), (0, 1))
    assert ed.colors == {(0, 0): (1, 2, 3)}
    assert ed.layout_slot_overrides == {"nonusbackslash": {"visible": False}}
    assert ed.lightbar_overlay == {"visible": True, "length": 0.8}
    assert ed._backdrop_mode_var.get() == "custom"
    assert ed._backdrop_mode_combo.value == "Custom image"
    assert ed.backdrop_transparency.get() == 42.0
    assert ed.canvas.reload_backdrop_calls == 1
    assert full_map_calls["n"] == 1
    assert ed.commit_calls == 1
    assert ed.overlay_controls.sync_calls == 1
    assert ed.lightbar_controls is not None
    assert ed.lightbar_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.status_label.text == "Active lighting profile: p2"
    assert ed.select_calls == ["K"]


def test_activate_profile_ui_keeps_activation_on_optional_backdrop_reload_failure(monkeypatch, caplog) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors, num_rows, num_cols, physical_layout):
        return ActivatedProfile(
            name="p2",
            keymap={"K": ((0, 0),)},
            layout_tweaks={},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
            layout_slot_overrides={},
            lightbar_overlay={},
        )

    monkeypatch.setattr(actions, "activate_profile", fake_activate_profile)
    monkeypatch.setattr(actions, "ensure_full_map_ui", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(actions.profiles, "load_backdrop_mode", lambda _name: "builtin")
    monkeypatch.setattr(actions.profiles, "load_backdrop_transparency", lambda _name: 15)

    class FailingVar:
        def set(self, _value) -> None:
            raise ValueError("broken ui var")

    ed = DummyEditor(
        _profile_name_var=DummyVar("p1"),
        config=object(),
        colors={(0, 0): (9, 9, 9)},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p1",
        selected_key_id="K",
        selected_slot_id="K",
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=DummyLightbarControls(),
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    ed._backdrop_mode_var = FailingVar()
    ed.backdrop_transparency = FailingVar()
    ed.canvas.reload_backdrop_error = RuntimeError("broken reload")

    caplog.set_level(logging.WARNING, logger=actions.__name__)

    actions_ui.activate_profile_ui(ed)

    assert ed.profile_name == "p2"
    assert ed._profile_name_var.get() == "p2"
    assert ed.commit_calls == 1
    assert ed.overlay_controls.sync_calls == 1
    assert ed.lightbar_controls is not None
    assert ed.lightbar_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.canvas.reload_backdrop_calls == 1
    assert ed.status_label.text == "Active lighting profile: p2"
    assert ed.select_calls == ["K"]
    assert "Failed to update per-profile backdrop mode UI during activation" in caplog.text
    assert "Failed to update per-profile backdrop transparency UI during activation" in caplog.text
    assert "Failed to reload per-profile backdrop image during activation" in caplog.text


def test_activate_profile_ui_propagates_unexpected_backdrop_reload_failures(monkeypatch) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors, num_rows, num_cols, physical_layout):
        return ActivatedProfile(
            name="p2",
            keymap={"K": ((0, 0),)},
            layout_tweaks={},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
            layout_slot_overrides={},
            lightbar_overlay={},
        )

    monkeypatch.setattr(actions, "activate_profile", fake_activate_profile)
    monkeypatch.setattr(actions, "ensure_full_map_ui", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(actions.profiles, "load_backdrop_mode", lambda _name: "builtin")
    monkeypatch.setattr(actions.profiles, "load_backdrop_transparency", lambda _name: 15)

    ed = DummyEditor(
        _profile_name_var=DummyVar("p1"),
        config=object(),
        colors={(0, 0): (9, 9, 9)},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p1",
        selected_key_id="K",
        selected_slot_id="K",
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=DummyLightbarControls(),
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    ed.canvas.reload_backdrop_error = AssertionError("broken reload")

    with pytest.raises(AssertionError):
        actions_ui.activate_profile_ui(ed)


def test_activate_profile_ui_handles_missing_optional_methods(monkeypatch) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors, num_rows, num_cols, physical_layout):
        return ActivatedProfile(
            name="p2",
            keymap={"K": ((0, 0),)},
            layout_tweaks={},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
            layout_slot_overrides={},
            lightbar_overlay={},
        )

    visible_identity_calls: list[tuple[str | None, str | None]] = []

    def fake_select_visible_identity(editor, *, slot_id, key_id) -> None:
        visible_identity_calls.append((slot_id, key_id))
        editor.selected_slot_id = slot_id
        editor.selected_key_id = key_id
        editor.selected_cells = keymap_cells_for(editor.keymap, key_id, slot_id=slot_id)
        editor.selected_cell = primary_cell(editor.selected_cells)

    monkeypatch.setattr(actions, "activate_profile", fake_activate_profile)
    monkeypatch.setattr(actions, "ensure_full_map_ui", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(actions.profiles, "load_backdrop_mode", lambda _name: "builtin")
    monkeypatch.setattr(actions.profiles, "load_backdrop_transparency", lambda _name: 15)
    monkeypatch.setattr(actions, "select_visible_identity", fake_select_visible_identity)
    monkeypatch.delattr(DummyEditor, "select_slot_id")
    monkeypatch.delattr(DummyEditor, "_refresh_layout_slot_controls")
    monkeypatch.delattr(DummyCanvas, "reload_backdrop_image")

    ed = DummyEditor(
        _profile_name_var=DummyVar("p1"),
        config=object(),
        colors={(0, 0): (9, 9, 9)},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p1",
        selected_key_id="K",
        selected_slot_id="K",
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=DummyLightbarControls(),
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    ed._backdrop_mode_var = DummyVar("none")
    ed.backdrop_transparency = DummyVar(0.0)
    ed._backdrop_mode_combo = DummySettable()

    actions_ui.activate_profile_ui(ed)

    assert ed.profile_name == "p2"
    assert ed.commit_calls == 1
    assert ed.overlay_controls.sync_calls == 1
    assert ed.lightbar_controls is not None
    assert ed.lightbar_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert visible_identity_calls == [("K", "K")]
    assert ed.selected_cells == ((0, 0),)
    assert ed.status_label.text == "Active lighting profile: p2"


def test_delete_profile_ui_updates_combo(monkeypatch) -> None:
    def fake_delete_profile(_name: str) -> DeleteProfileResult:
        return DeleteProfileResult(deleted=True, active_profile="default", message="Deleted lighting profile: p2")

    monkeypatch.setattr(actions, "delete_profile", fake_delete_profile)
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["default", "p3"])  # type: ignore[attr-defined]

    ed = DummyEditor(
        _profile_name_var=DummyVar("p2"),
        config=object(),
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p2",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )

    actions_ui.delete_profile_ui(ed)

    assert ed.profile_name == "default"
    assert ed._profile_name_var.get() == "default"
    assert ed._profiles_combo.values == ["default", "p3"]
    assert ed.status_label.text == "Deleted lighting profile: p2"


def test_delete_profile_ui_activates_fallback_scene_when_editor_supports_it(monkeypatch) -> None:
    fallback_calls: list[bool] = []
    monkeypatch.setattr(
        actions,
        "delete_profile",
        lambda _name: DeleteProfileResult(deleted=True, active_profile="default", message="deleted"),
    )
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["default"])  # type: ignore[attr-defined]
    ed = DummyEditor(
        _profile_name_var=DummyVar("p2"),
        config=object(),
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="p2",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
        _activate_profile=lambda: fallback_calls.append(True),
    )

    actions_ui.delete_profile_ui(ed)

    assert fallback_calls == [True]


def test_save_power_source_profile_policy_ui_persists_selection_and_refreshes_options(monkeypatch) -> None:
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["default", "gaming"])  # type: ignore[attr-defined]
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: None)

    config = SimpleNamespace(ac_perkey_profile_name=None, battery_perkey_profile_name="movie")
    ed = DummyEditor(
        _profile_name_var=DummyVar("default"),
        config=config,
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar("gaming"),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )

    actions_ui.save_power_source_profile_policy_ui(ed)

    assert config.ac_perkey_profile_name == "gaming"
    assert config.battery_perkey_profile_name is None
    assert ed._ac_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
    ]
    assert ed._battery_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
    ]
    assert ed.status_label.text == "Saved AC/battery lighting profile policy"


def test_save_power_source_profile_policy_ui_activates_current_ac_profile_when_needed(monkeypatch) -> None:
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["Blue", "Purple"])  # type: ignore[attr-defined]
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: True)

    activation_calls: list[str] = []

    def fake_activate_profile_ui(editor) -> None:
        activation_calls.append(editor._profile_name_var.get())
        editor.profile_name = editor._profile_name_var.get()

    monkeypatch.setattr(actions_ui, "activate_profile_ui", fake_activate_profile_ui)

    config = SimpleNamespace(ac_perkey_profile_name=None, battery_perkey_profile_name="Blue")
    ed = DummyEditor(
        _profile_name_var=DummyVar("Blue"),
        config=config,
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="Blue",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar("Purple"),
        _battery_power_source_profile_var=DummyVar("Blue"),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )

    actions_ui.save_power_source_profile_policy_ui(ed)

    assert config.ac_perkey_profile_name == "Purple"
    assert config.battery_perkey_profile_name == "Blue"
    assert ed.profile_name == "Purple"
    assert ed._profile_name_var.get() == "Purple"
    assert activation_calls == ["Purple"]
    assert ed.status_label.text == "Saved AC/battery lighting profile policy and activated 'Purple' for AC"


def test_sync_power_source_profile_policy_controls_keeps_missing_configured_profile_visible(monkeypatch) -> None:
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["default", "gaming"])  # type: ignore[attr-defined]

    config = SimpleNamespace(ac_perkey_profile_name="movie", battery_perkey_profile_name=None)
    ed = DummyEditor(
        _profile_name_var=DummyVar("default"),
        config=config,
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )

    actions_ui.sync_power_source_profile_policy_controls(ed)

    assert ed._ac_power_source_profile_var.get() == "movie"
    assert ed._battery_power_source_profile_var.get() == actions_ui.KEEP_CURRENT_PROFILE_LABEL
    assert ed._ac_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
        "movie",
    ]


def test_reset_layout_defaults_ui_reloads_selected_layout_bundle(monkeypatch) -> None:
    monkeypatch.setattr(actions, "get_default_keymap", lambda _layout_id: {"nonusbackslash": "1,2", "enter": "2,14"})
    monkeypatch.setattr(actions, "get_default_layout_tweaks", lambda _layout_id: {"dx": 1.0})
    monkeypatch.setattr(actions, "get_default_per_key_tweaks", lambda _layout_id: {"nonusbackslash": {"dx": 2.0}})
    monkeypatch.setattr(
        actions,
        "get_layout_keys",
        lambda _layout_id, **_kwargs: [type("K", (), {"key_id": "nonusbackslash"})()],
    )
    monkeypatch.setattr(actions, "resolve_layout_id", lambda _layout_id: "iso")
    monkeypatch.setattr(actions.profiles, "save_layout_slots", lambda *_args, **_kwargs: {})

    ed = DummyEditor(
        _profile_name_var=DummyVar("p2"),
        config=object(),
        colors={},
        keymap={"old": ((0, 0),)},
        _physical_layout="auto",
        layout_tweaks={"dx": 9.0},
        per_key_layout_tweaks={"old": {"dx": 1.0}},
        layout_slot_overrides={"nonusbackslash": {"visible": False}},
        profile_name="p2",
        selected_key_id="old",
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
    )

    actions.reset_layout_defaults_ui(ed)

    assert ed.keymap == {
        "nonusbackslash": ((1, 2),),
        str(slot_id_for_key_id("auto", "enter") or "enter"): ((2, 14),),
    }
    assert ed.layout_tweaks == {"dx": 1.0}
    assert ed.per_key_layout_tweaks == {"nonusbackslash": {"dx": 2.0}}
    assert ed.layout_slot_overrides == {}
    assert ed.selected_key_id == "nonusbackslash"
    assert ed.selected_slot_id == "nonusbackslash"
    assert ed.selected_cells == ((1, 2),)
    assert ed.selected_cell == (1, 2)
    assert ed.overlay_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.status_label.text == "Reset to ISO (102/105-key) layout defaults"
    assert ed.select_calls == ["nonusbackslash"]


def test_configured_power_source_names_and_maybe_activate(monkeypatch) -> None:
    ed = DummyEditor(
        _profile_name_var=DummyVar("Default"),
        config=SimpleNamespace(ac_perkey_profile_name="gaming", battery_perkey_profile_name=""),
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="Default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar("ghost-profile"),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )

    monkeypatch.setattr(actions_ui.profiles, "list_profiles", lambda: ["Default"])
    names = actions_ui._configured_power_source_profile_names(ed)
    assert "gaming" in names
    assert "ghost-profile" in names

    opts = actions_ui.power_source_profile_options(ed)
    assert opts[0] == actions_ui.KEEP_CURRENT_PROFILE_LABEL
    assert "ghost-profile" in opts

    # read_on_ac failure
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: (_ for _ in ()).throw(OSError("no ac")))
    assert actions_ui._maybe_activate_current_power_source_profile_ui(ed) is None

    monkeypatch.setattr(actions, "read_on_ac_power", lambda: None)
    assert actions_ui._maybe_activate_current_power_source_profile_ui(ed) is None

    # already on desired profile
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: True)
    ed._ac_power_source_profile_var = DummyVar("Default")
    ed.profile_name = "Default"
    assert actions_ui._maybe_activate_current_power_source_profile_ui(ed) is None

    # activate other
    activated: list[str] = []
    monkeypatch.setattr(
        actions_ui, "activate_profile_ui", lambda editor: activated.append(editor._profile_name_var.get())
    )
    ed._ac_power_source_profile_var = DummyVar("gaming")
    ed.profile_name = "Default"
    result = actions_ui._maybe_activate_current_power_source_profile_ui(ed)
    assert result == ("AC", "gaming")
    assert activated == ["gaming"]


def test_save_profile_ui_and_new_profile_paths(monkeypatch) -> None:
    statuses: list[str] = []
    commits: list[bool] = []
    marks: list[str] = []

    ed = DummyEditor(
        _profile_name_var=DummyVar("Night"),
        config=SimpleNamespace(),
        colors={(0, 0): (1, 2, 3)},
        keymap={"esc": ((0, 0),)},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="Default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=DummyLightbarControls(),
        lightbar_overlay={"enabled": True},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    ed.secondary_lighting = {"version": 1}
    ed._commit = lambda *, force=False: commits.append(force)
    ed.root = object()

    monkeypatch.setattr(actions, "save_profile", lambda name, **_k: name)
    monkeypatch.setattr(actions, "ensure_full_map_ui", lambda *_a, **_k: None)
    monkeypatch.setattr(actions, "_mark_saved_snapshot_if_supported", lambda _e: marks.append("mark"))
    monkeypatch.setattr(actions, "set_status", lambda _e, msg: statuses.append(msg))
    monkeypatch.setattr(actions, "saved_profile", lambda name: f"saved:{name}")
    monkeypatch.setattr(actions_ui.profiles, "list_profiles", lambda: ["Default", "Night"])

    actions_ui.save_profile_ui(ed)
    assert ed.profile_name == "Night"
    assert commits == [True]
    assert marks == ["mark"]
    assert statuses[-1] == "saved:Night"

    # new profile cancelled / empty / exists / success
    monkeypatch.setattr(actions, "_guard_destructive_profile_action", lambda *_a, **_k: False)
    actions_ui.new_profile_ui(ed)
    assert "Created" not in "".join(statuses)

    monkeypatch.setattr(actions, "_guard_destructive_profile_action", lambda *_a, **_k: True)

    import tkinter.simpledialog as sd

    monkeypatch.setattr(sd, "askstring", lambda *_a, **_k: None)
    actions_ui.new_profile_ui(ed)

    monkeypatch.setattr(sd, "askstring", lambda *_a, **_k: "   ")
    actions_ui.new_profile_ui(ed)
    assert any("cannot be empty" in s for s in statuses)

    monkeypatch.setattr(sd, "askstring", lambda *_a, **_k: "Default")
    actions_ui.new_profile_ui(ed)
    assert any("already exists" in s for s in statuses)

    monkeypatch.setattr(sd, "askstring", lambda *_a, **_k: "Fresh")
    # list_profiles is called twice (existence check + combo refresh); return
    # pre-create list first, then include the new name.
    profile_lists = iter([["Default", "Night"], ["Default", "Night", "Fresh"], ["Default", "Night", "Fresh"]])
    monkeypatch.setattr(actions_ui.profiles, "list_profiles", lambda: next(profile_lists))
    statuses.clear()
    actions_ui.new_profile_ui(ed)
    assert ed.profile_name == "Fresh"
    assert any("Created lighting profile" in s for s in statuses)


def test_delete_and_set_default_guard_paths(monkeypatch) -> None:
    statuses: list[str] = []
    ed = DummyEditor(
        _profile_name_var=DummyVar("Default"),
        config=SimpleNamespace(),
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="Default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    monkeypatch.setattr(actions, "set_status", lambda _e, msg: statuses.append(msg))
    monkeypatch.setattr(actions, "_guard_destructive_profile_action", lambda *_a, **_k: False)
    actions_ui.delete_profile_ui(ed)
    assert statuses == []

    monkeypatch.setattr(actions, "_guard_destructive_profile_action", lambda *_a, **_k: True)
    monkeypatch.setattr(
        actions,
        "delete_profile",
        lambda _name: SimpleNamespace(deleted=False, message="cannot delete", active_profile="Default"),
    )
    actions_ui.delete_profile_ui(ed)
    assert statuses[-1] == "cannot delete"

    monkeypatch.setattr(actions, "default_profile_set", lambda name: f"default:{name}")
    monkeypatch.setattr(actions_ui.profiles, "set_default_profile", lambda name: name)
    actions_ui.set_default_profile_ui(ed)
    assert statuses[-1] == "default:Default"


def test_activate_profile_ui_guard_blocks(monkeypatch) -> None:
    ed = DummyEditor(
        _profile_name_var=DummyVar("Other"),
        config=SimpleNamespace(),
        colors={},
        keymap={},
        _physical_layout="ansi",
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        profile_name="Default",
        selected_key_id=None,
        selected_slot_id=None,
        overlay_controls=DummyOverlayControls(),
        lightbar_controls=None,
        lightbar_overlay={},
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
        _ac_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _battery_power_source_profile_var=DummyVar(actions_ui.KEEP_CURRENT_PROFILE_LABEL),
        _ac_power_source_profile_combo=DummyCombo(),
        _battery_power_source_profile_combo=DummyCombo(),
    )
    monkeypatch.setattr(actions, "_guard_destructive_profile_action", lambda *_a, **_k: False)
    called = []
    monkeypatch.setattr(actions, "activate_profile", lambda *_a, **_k: called.append("x"))
    actions_ui.activate_profile_ui(ed)
    assert called == []
