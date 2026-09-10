"""Layout-default reset UI covered alongside power-source profiles."""

import keyrgb.gui.perkey.ui.profile_actions as actions
from keyrgb.core.resources.layouts import slot_id_for_key_id
from tests.gui.perkey.editor.ui.power_source._power_source_fakes import (
    DummyCanvas,
    DummyCombo,
    DummyEditor,
    DummyLabel,
    DummyOverlayControls,
    DummyVar,
)


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
