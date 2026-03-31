from __future__ import annotations

from dataclasses import dataclass

import src.gui.perkey.ui.profile_actions as actions
from src.gui.perkey.profile_management import ActivatedProfile, DeleteProfileResult


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

    def redraw(self) -> None:
        self.redraw_calls += 1


class DummyOverlayControls:
    def __init__(self):
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


class DummyCombo:
    def __init__(self):
        self.values = None

    def configure(self, *, values):
        self.values = list(values)


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
    overlay_controls: DummyOverlayControls
    canvas: DummyCanvas
    status_label: DummyLabel
    _profiles_combo: DummyCombo
    commit_calls: int = 0
    select_calls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.select_calls is None:
            self.select_calls = []

    def _commit(self, *, force: bool = False) -> None:
        self.commit_calls += 1

    def select_key_id(self, key_id: str) -> None:
        self.selected_key_id = key_id
        self.selected_cell = self.keymap.get(key_id)
        self.select_calls.append(key_id)

    def _refresh_layout_slot_controls(self) -> None:
        return None


def test_activate_profile_ui_updates_state_and_redraws(monkeypatch) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors, num_rows, num_cols, physical_layout):
        assert num_rows > 0
        assert num_cols > 0
        assert physical_layout == "ansi"
        return ActivatedProfile(
            name="p2",
            keymap={"K": (0, 0)},
            layout_tweaks={"dx": 1.0},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
            layout_slot_overrides={"nonusbackslash": {"visible": False}},
        )

    monkeypatch.setattr(actions, "activate_profile", fake_activate_profile)

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
        overlay_controls=DummyOverlayControls(),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
    )

    actions.activate_profile_ui(ed)

    assert ed.profile_name == "p2"
    assert ed._profile_name_var.get() == "p2"
    assert ed.keymap == {"K": (0, 0)}
    assert ed.colors == {(0, 0): (1, 2, 3)}
    assert ed.layout_slot_overrides == {"nonusbackslash": {"visible": False}}
    assert full_map_calls["n"] == 1
    assert ed.commit_calls == 1
    assert ed.overlay_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.status_label.text == "Active lighting profile: p2"
    assert ed.select_calls == ["K"]


def test_delete_profile_ui_updates_combo(monkeypatch) -> None:
    def fake_delete_profile(_name: str) -> DeleteProfileResult:
        return DeleteProfileResult(deleted=True, active_profile="light", message="Deleted lighting profile: p2")

    monkeypatch.setattr(actions, "delete_profile", fake_delete_profile)
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["light", "p3"])  # type: ignore[attr-defined]

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
        overlay_controls=DummyOverlayControls(),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
    )

    actions.delete_profile_ui(ed)

    assert ed.profile_name == "light"
    assert ed._profile_name_var.get() == "light"
    assert ed._profiles_combo.values == ["light", "p3"]
    assert ed.status_label.text == "Deleted lighting profile: p2"


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
        keymap={"old": (0, 0)},
        _physical_layout="auto",
        layout_tweaks={"dx": 9.0},
        per_key_layout_tweaks={"old": {"dx": 1.0}},
        layout_slot_overrides={"nonusbackslash": {"visible": False}},
        profile_name="p2",
        selected_key_id="old",
        overlay_controls=DummyOverlayControls(),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
    )

    actions.reset_layout_defaults_ui(ed)

    assert ed.keymap == {"nonusbackslash": (1, 2), "enter": (2, 14)}
    assert ed.layout_tweaks == {"dx": 1.0}
    assert ed.per_key_layout_tweaks == {"nonusbackslash": {"dx": 2.0}}
    assert ed.layout_slot_overrides == {}
    assert ed.selected_key_id == "nonusbackslash"
    assert ed.selected_cell == (1, 2)
    assert ed.overlay_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.status_label.text == "Reset to ISO (102/105-key) layout defaults"
    assert ed.select_calls == ["nonusbackslash"]
