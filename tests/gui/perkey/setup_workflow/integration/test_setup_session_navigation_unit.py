"""Guided-setup session files, navigation, and child-lifecycle unit tests.

Split out of ``test_setup_integration_unit.py`` to keep test modules under
the LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from keyrgb.gui.calibrator.guided import GUIDED_SESSION_RESULT_VERSION, write_guided_result
from keyrgb.gui.perkey.setup_workflow import integration
from keyrgb.gui.perkey.setup_workflow.integration import (
    GuidedSetupController,
    SetupStep,
    build_setup_commit_callbacks,
    cleanup_guided_session,
    create_guided_session_file,
    legend_pack_choices,
    optional_slot_states,
    read_guided_result,
)
from keyrgb.gui.perkey.setup_workflow.model import SetupSource, draft_from_source
from tests.gui.perkey.setup_workflow._setup_fakes import (
    COLS,
    ROWS,
    VALID_KEYMAP,
    FakeConfig,
    FakeEditor,
    FakeProfiles,
    _brightness_only_caps,
    _make_controller,
    _snapshot_env,
)

# -- catalog / legend / slot helpers ------------------------------------


def test_available_layouts_follow_catalog_order() -> None:
    from keyrgb.gui.perkey.setup_workflow.integration import available_layouts

    layouts = available_layouts()

    assert layouts[0][0] == "auto"
    assert ("ansi", "ANSI (101/104-key)") in layouts


def test_legend_pack_choices_start_with_auto() -> None:
    choices = legend_pack_choices("ansi")

    assert choices[0] == ("auto", "Default legends")
    assert len({pack_id for pack_id, _ in choices}) == len(choices)


def test_optional_slot_states_follow_draft() -> None:
    draft = draft_from_source(SetupSource(physical_layout="ansi", legend_pack="auto"))

    states = optional_slot_states(draft)

    assert states
    assert {str(state.key_id) for state in states} >= {"fn", "menu"}
    assert all(str(state.slot_id) for state in states)


# -- guided session temp files -------------------------------------------


def test_session_roundtrip_and_cleanup() -> None:
    draft = draft_from_source(
        SetupSource(physical_layout="ansi", legend_pack="auto", keymap=dict(VALID_KEYMAP)),
    )

    session_path = create_guided_session_file(draft, rows=ROWS, cols=COLS)
    try:
        assert session_path.exists()
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        assert payload["physical_layout"] == "ansi"
        assert payload["legend_pack"] == "auto"
        assert payload["dimensions"] == [ROWS, COLS]

        write_guided_result(session_path, {"a": ((0, 0),), "b": ((1, 2),)}, physical_layout="ansi")
        adopted = read_guided_result(session_path, rows=ROWS, cols=COLS, expected_layout="ansi")

        # Identities canonicalize to slot IDs; cells survive verbatim.
        assert len(adopted) == 2
        assert {cell for cells in adopted.values() for cell in cells} == {(0, 0), (1, 2)}
    finally:
        cleanup_guided_session(session_path)
    assert not session_path.exists()
    assert not session_path.parent.exists()


def test_read_result_rejects_bad_version_layout_and_empty(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(
        json.dumps({"physical_layout": "ansi", "result": {"keymap": {}, "physical_layout": "ansi", "version": 999}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="version"):
        read_guided_result(session_path, rows=ROWS, cols=COLS, expected_layout="ansi")

    write_guided_result(session_path, {"a": ((0, 0),)}, physical_layout="iso")
    session_path.write_text(
        json.dumps(
            {
                "physical_layout": "ansi",
                "result": {"keymap": {"a": "0,0"}, "physical_layout": "iso", "version": GUIDED_SESSION_RESULT_VERSION},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="layout"):
        read_guided_result(session_path, rows=ROWS, cols=COLS, expected_layout="ansi")

    session_path.write_text(json.dumps({"physical_layout": "ansi"}), encoding="utf-8")
    with pytest.raises(TypeError, match="no calibrator result"):
        read_guided_result(session_path, rows=ROWS, cols=COLS, expected_layout="ansi")

    session_path.write_text(
        json.dumps(
            {
                "physical_layout": "ansi",
                "result": {
                    "keymap": {"a": "9,9"},
                    "physical_layout": "ansi",
                    "version": GUIDED_SESSION_RESULT_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no usable cells"):
        read_guided_result(session_path, rows=ROWS, cols=COLS, expected_layout="ansi")


def test_cleanup_guided_session_tolerates_missing() -> None:
    cleanup_guided_session(None)
    cleanup_guided_session("/nonexistent-dir-xyz/session.json")


# -- navigation performs zero writes -------------------------------------


def test_navigation_and_cancel_perform_zero_writes(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))

    assert controller.current_step is SetupStep.PREFLIGHT
    for _ in range(len(controller.steps)):
        assert controller.go_next() is True
    assert controller.current_step is SetupStep.REVIEW
    for _ in range(len(controller.steps)):
        assert controller.go_back() is True

    assert profiles.calls == []
    assert editor.config.batches == 0
    assert editor.commits == 0


def test_config_only_invalid_keymap_cannot_advance_but_valid_can(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.keymap = {}
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=False))
    while controller.current_step is not SetupStep.CALIBRATION:
        assert controller.go_next() is True

    assert controller.may_skip_calibration() is False
    assert controller.go_next() is False
    assert "live key flashing is unavailable" in controller.last_message
    assert profiles.calls == []

    controller.draft.set_keymap(dict(VALID_KEYMAP))
    assert controller.may_skip_calibration() is True
    assert controller.go_next() is True


def test_config_only_never_launches_guided_calibrator(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    controller = _make_controller(editor, FakeProfiles(), env=_snapshot_env(per_key=False))

    allowed, message = controller.can_launch_calibrator()

    assert allowed is False
    assert "config-only" in message


# -- child lifecycle ------------------------------------------------------


def test_child_running_blocks_nav_close_and_finish(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    controller = _make_controller(editor, profiles, env=_snapshot_env(per_key=True))
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    try:
        controller.note_child_started(session_path)

        allowed, message = controller.close_allowed()
        assert allowed is False
        assert "never terminated" in message
        assert controller.go_next() is False
        assert controller.go_back() is False
        assert controller.finish_allowed()[0] is False

        callbacks = build_setup_commit_callbacks(editor, controller.draft, config_only=False, profiles_module=profiles)
        gated = controller.finish(callbacks)
        assert gated.ok is False
        assert gated.stage == "gate"
        assert profiles.calls == []
        assert editor.commits == 0

        controller.note_child_finished()
        assert controller.close_allowed() == (True, "")
    finally:
        cleanup_guided_session(session_path)


def test_adopt_guided_result_updates_draft_and_cleans_up() -> None:
    draft = draft_from_source(SetupSource(physical_layout="ansi", keymap={}))
    from keyrgb.gui.perkey.setup_workflow.preflight import CalibrationPreflightEvidence, evaluate_calibration_preflight

    preflight = evaluate_calibration_preflight(
        CalibrationPreflightEvidence(
            selected_capabilities=_brightness_only_caps(), backend_name="Fake", dimensions=(ROWS, COLS)
        )
    )
    controller = GuidedSetupController(draft=draft, preflight=preflight, rows=ROWS, cols=COLS)
    session_path = create_guided_session_file(controller.draft, rows=ROWS, cols=COLS)
    write_guided_result(session_path, {"a": ((0, 0),), "b": ((1, 2),)}, physical_layout="ansi")
    controller.note_child_started(session_path)

    adopted, message = integration.adopt_guided_result(controller)

    assert adopted is True
    assert "adopted" in message
    assert controller.child_running is False
    assert len(controller.draft.keymap) == 2
    assert {cell for cells in controller.draft.keymap.values() for cell in list(cells)} == {(0, 0), (1, 2)}
    assert not session_path.exists()
    assert controller.may_skip_calibration() is True


def test_adopt_guided_result_without_result_keeps_draft() -> None:
    draft = draft_from_source(SetupSource(physical_layout="ansi", keymap=dict(VALID_KEYMAP)))
    from keyrgb.gui.perkey.setup_workflow.preflight import CalibrationPreflightEvidence, evaluate_calibration_preflight

    preflight = evaluate_calibration_preflight(
        CalibrationPreflightEvidence(
            selected_capabilities=_brightness_only_caps(), backend_name="Fake", dimensions=(ROWS, COLS)
        )
    )
    controller = GuidedSetupController(draft=draft, preflight=preflight, rows=ROWS, cols=COLS)
    session_path = create_guided_session_file(controller.draft, rows=ROWS, cols=COLS)
    controller.note_child_started(session_path)

    adopted, _ = integration.adopt_guided_result(controller)

    assert adopted is False
    assert controller.child_running is False
    assert controller.draft.keymap == VALID_KEYMAP
    assert not session_path.exists()
