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
    layout_tweaks: dict
    per_key_layout_tweaks: dict
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
        self.select_calls.append(key_id)


def test_activate_profile_ui_updates_state_and_redraws(monkeypatch) -> None:
    def fake_activate_profile(_name: str, *, config, current_colors):
        return ActivatedProfile(
            name="p2",
            keymap={"K": (0, 0)},
            layout_tweaks={"dx": 1.0},
            per_key_layout_tweaks={},
            colors={(0, 0): (1, 2, 3)},
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
        layout_tweaks={},
        per_key_layout_tweaks={},
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
    assert full_map_calls["n"] == 1
    assert ed.commit_calls == 1
    assert ed.overlay_controls.sync_calls == 1
    assert ed.canvas.redraw_calls == 1
    assert ed.status_label.text == "Active profile: p2"
    assert ed.select_calls == ["K"]


def test_delete_profile_ui_updates_combo(monkeypatch) -> None:
    def fake_delete_profile(_name: str) -> DeleteProfileResult:
        return DeleteProfileResult(deleted=True, active_profile="default", message="Deleted profile: p2")

    monkeypatch.setattr(actions, "delete_profile", fake_delete_profile)
    monkeypatch.setattr(actions.profiles, "list_profiles", lambda: ["default", "p3"])  # type: ignore[attr-defined]

    ed = DummyEditor(
        _profile_name_var=DummyVar("p2"),
        config=object(),
        colors={},
        keymap={},
        layout_tweaks={},
        per_key_layout_tweaks={},
        profile_name="p2",
        selected_key_id=None,
        overlay_controls=DummyOverlayControls(),
        canvas=DummyCanvas(),
        status_label=DummyLabel(),
        _profiles_combo=DummyCombo(),
    )

    actions.delete_profile_ui(ed)

    assert ed.profile_name == "default"
    assert ed._profile_name_var.get() == "default"
    assert ed._profiles_combo.values == ["default", "p3"]
    assert ed.status_label.text == "Deleted profile: p2"
