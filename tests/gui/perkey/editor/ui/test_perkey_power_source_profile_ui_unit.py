from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import keyrgb.gui.perkey.ui._profile_actions_ui as actions_ui
import keyrgb.gui.perkey.ui.profile_actions as actions
from keyrgb.core.resources.layouts import slot_id_for_key_id
from keyrgb.gui.perkey.profile_management import keymap_cells_for, primary_cell


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
