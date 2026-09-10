"""AC/battery power-source profile policy UI."""

from types import SimpleNamespace

import keyrgb.gui.perkey.ui._profile_actions_ui as actions_ui
import keyrgb.gui.perkey.ui.profile_actions as actions
from tests.gui.perkey.editor.ui.power_source._power_source_fakes import (
    DummyCanvas,
    DummyCombo,
    DummyConfig,
    DummyEditor,
    DummyLabel,
    DummyOverlayControls,
    DummyVar,
)


def test_save_power_source_profile_policy_ui_uses_cached_snapshot_without_scanning(monkeypatch) -> None:
    def _boom() -> list[str]:
        raise AssertionError("list_profiles must not be called when a snapshot is cached")

    monkeypatch.setattr(actions_ui.profiles, "list_profiles", _boom)
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: None)

    config = DummyConfig(ac_perkey_profile_name=None, battery_perkey_profile_name="movie")
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
    # Production editors carry the immutable construction snapshot; policy
    # selection must reuse it instead of scanning the filesystem.
    ed._profile_names_snapshot = ("default", "gaming")

    actions_ui.save_power_source_profile_policy_ui(ed)

    assert config.ac_perkey_profile_name == "gaming"
    assert config.battery_perkey_profile_name is None
    assert config.batch_update_calls == 1
    assert ed._profile_names_snapshot == ("default", "gaming")
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
    monkeypatch.setattr(actions, "read_on_ac_power", lambda: True)

    activation_calls: list[str] = []

    def fake_activate_profile_ui(editor) -> None:
        activation_calls.append(editor._profile_name_var.get())
        editor.profile_name = editor._profile_name_var.get()

    monkeypatch.setattr(actions_ui, "activate_profile_ui", fake_activate_profile_ui)

    config = DummyConfig(ac_perkey_profile_name=None, battery_perkey_profile_name="Blue")
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
    ed._profile_names_snapshot = ("Blue", "Purple")

    actions_ui.save_power_source_profile_policy_ui(ed)

    assert config.ac_perkey_profile_name == "Purple"
    assert config.battery_perkey_profile_name == "Blue"
    assert config.batch_update_calls == 1
    assert ed.profile_name == "Purple"
    assert ed._profile_name_var.get() == "Purple"
    assert activation_calls == ["Purple"]
    assert ed.status_label.text == "Saved AC/battery lighting profile policy and activated 'Purple' for AC"


def test_sync_power_source_profile_policy_controls_keeps_missing_configured_profile_visible() -> None:
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

    actions_ui.sync_power_source_profile_policy_controls(ed, ("default", "gaming"))

    assert ed._ac_power_source_profile_var.get() == "movie"
    assert ed._battery_power_source_profile_var.get() == actions_ui.KEEP_CURRENT_PROFILE_LABEL
    assert ed._ac_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
        "movie",
    ]


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

    names = actions_ui._configured_power_source_profile_names(ed)
    assert "gaming" in names
    assert "ghost-profile" in names

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


def test_refresh_all_profile_choices_uses_single_shared_scan(monkeypatch) -> None:
    list_calls = 0

    def _list_profiles() -> list[str]:
        nonlocal list_calls
        list_calls += 1
        return ["default", "gaming"]

    monkeypatch.setattr(actions_ui.profiles, "list_profiles", _list_profiles)
    config = SimpleNamespace(ac_perkey_profile_name="ghost", battery_perkey_profile_name=None)
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

    actions_ui.refresh_all_profile_choices(ed)

    assert list_calls == 1
    assert ed._profile_names_snapshot == ("default", "gaming")
    assert ed._profiles_combo.values == ["default", "gaming"]
    # Configured-but-missing value is preserved without any filesystem scan.
    assert ed._ac_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
        "ghost",
    ]
    assert ed._battery_power_source_profile_combo.values == [
        "Keep current profile",
        "default",
        "gaming",
        "ghost",
    ]
