"""Guided-setup commit-adapter unit tests.

Split out of ``test_setup_integration_unit.py`` to keep test modules under
the LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.profile import profiles as real_profiles
from keyrgb.gui.perkey.setup_workflow.integration import (
    build_setup_commit_callbacks,
    capture_setup_source,
)
from keyrgb.gui.perkey.setup_workflow.model import draft_from_source
from keyrgb.gui.perkey.setup_workflow.transaction import finish_setup
from tests.gui.perkey.setup_workflow._setup_fakes import (
    OTHER_KEYMAP,
    VALID_KEYMAP,
    FakeConfig,
    FakeEditor,
    FakeProfiles,
    _make_controller,
    _snapshot_env,
)

# -- commit adapter --------------------------------------------------------


def test_finish_live_commits_once_with_hardware_apply(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))
    controller.draft.set_physical_layout("iso")
    controller.draft.set_keymap(dict(OTHER_KEYMAP))
    callbacks = build_setup_commit_callbacks(editor, controller.draft, config_only=False, profiles_module=profiles)

    result = controller.finish(callbacks)

    assert result.ok is True
    assert editor._physical_layout == "iso"
    assert editor.keymap == OTHER_KEYMAP
    assert editor.config.physical_layout == "iso"
    assert editor.commits == 1
    kinds = [call[0] for call in profiles.calls]
    assert kinds == ["save_keymap", "save_layout_global", "save_layout_per_key", "save_layout_slots"]
    assert editor.canvas.redraws >= 1
    assert editor.overlay_controls.syncs >= 1
    assert editor.slot_control_refreshes >= 1
    assert editor.visible_syncs >= 1
    assert editor._layout_var.get() == "iso"


def test_finish_config_only_skips_hardware_apply(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))
    callbacks = build_setup_commit_callbacks(editor, controller.draft, config_only=True, profiles_module=profiles)

    assert callbacks.apply_hardware is None
    result = finish_setup(controller.draft, callbacks)

    assert result.ok is True
    assert editor.commits == 0
    assert [call[0] for call in profiles.calls] == [
        "save_keymap",
        "save_layout_global",
        "save_layout_per_key",
        "save_layout_slots",
    ]
    # No unrelated payloads are saved through this boundary.
    assert all(call[0].startswith("save_keymap") or "layout" in call[0] for call in profiles.calls)


def test_failed_finish_rolls_back_memory_and_persisted_state(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles(fail_on="save_keymap")
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))
    controller.draft.set_physical_layout("iso")
    controller.draft.set_keymap(dict(OTHER_KEYMAP))
    callbacks = build_setup_commit_callbacks(editor, controller.draft, config_only=False, profiles_module=profiles)

    result = controller.finish(callbacks)

    assert result.ok is False
    assert result.rolled_back is True
    # In-memory editor state is back to the original setup.
    assert editor._physical_layout == "ansi"
    assert editor.keymap == VALID_KEYMAP
    # Persisted config + profile state is back to the original setup.
    assert editor.config.physical_layout == "ansi"
    assert editor.config.layout_legend_pack == "auto"
    save_calls = [call for call in profiles.calls if call[0] == "save_keymap"]
    assert len(save_calls) == 2  # draft attempt, then original restore
    assert save_calls[-1][3] == "ansi"
    # Draft edits are kept so the modal stays open for retry.
    assert controller.draft.physical_layout == "iso"
    assert editor.commits == 0


def test_build_callbacks_requires_config(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.config = None  # type: ignore[assignment]
    draft = draft_from_source(capture_setup_source(editor))
    with pytest.raises(ValueError, match="no config"):
        build_setup_commit_callbacks(editor, draft, config_only=True, profiles_module=FakeProfiles())


def test_overlay_edits_leave_per_key_payloads_untouched(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.per_key_layout_tweaks = {"a": {"dx": 0.25}}
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))

    controller.draft.set_layout_tweak("dx", 1.5)
    controller.draft.set_layout_tweak("inset", 0.12)
    callbacks = build_setup_commit_callbacks(editor, controller.draft, config_only=True, profiles_module=profiles)
    result = controller.finish(callbacks)

    assert result.ok is True
    assert editor.layout_tweaks["dx"] == 1.5
    expected_per_key = real_profiles.normalize_layout_per_key_tweaks({"a": {"dx": 0.25}}, physical_layout="ansi")
    assert editor.per_key_layout_tweaks == expected_per_key
    per_key_saves = [call for call in profiles.calls if call[0] == "save_layout_per_key"]
    assert per_key_saves and per_key_saves[-1][1] == expected_per_key
