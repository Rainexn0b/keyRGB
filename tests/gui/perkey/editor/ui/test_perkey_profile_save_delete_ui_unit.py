from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import keyrgb.gui.perkey.ui._profile_actions_ui as actions_ui
import keyrgb.gui.perkey.ui.profile_actions as actions
from keyrgb.core.resources.layouts import slot_id_for_key_id
from keyrgb.gui.perkey.profile_management import DeleteProfileResult, keymap_cells_for, primary_cell


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
