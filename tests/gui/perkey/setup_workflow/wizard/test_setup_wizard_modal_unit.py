"""Guided-setup modal-contract unit tests (FakeDialog double).

Split out of ``test_setup_wizard_unit.py`` to keep test modules under the
LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from keyrgb.core.profile import profiles as real_profiles
from keyrgb.gui.perkey.setup_workflow import integration
from keyrgb.gui.perkey.setup_workflow.integration import (
    SetupStep,
    create_guided_session_file,
    resolve_setup_preflight,
)
from keyrgb.gui.perkey.setup_workflow.preflight import PreflightMode
from keyrgb.gui.perkey.setup_workflow.wizard import WIZARD_ATTR, GuidedSetupWizard
from keyrgb.tray.ui.gui_launch import build_perkey_preflight_payload
from tests.gui.perkey.setup_workflow._setup_fakes import (
    COLS,
    OTHER_KEYMAP,
    ROWS,
    VALID_KEYMAP,
    FakeBackend,
    FakeConfig,
    FakeEditor,
    FakeHardwareModule,
    FakeProfiles,
    _per_key_caps,
    _snapshot_env,
)
from tests.gui.perkey.setup_workflow._setup_wizard_fakes import (
    _open,
)

# -- singleton -----------------------------------------------------------


def test_open_focuses_existing_wizard_singleton(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    first = _open(editor)
    second = _open(editor)

    assert second is first
    assert first.focus_calls == 1
    assert getattr(editor, WIZARD_ATTR) is first


def test_open_replaces_dead_wizard(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    first = _open(editor)
    first.alive = False
    second = _open(editor)

    assert second is not first
    assert getattr(editor, WIZARD_ATTR) is second


def test_open_builds_controller_from_editor_and_snapshot(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    dialog = _open(editor, env=_snapshot_env(per_key=True))

    assert dialog.controller.draft.physical_layout == "ansi"
    assert dialog.controller.preflight.mode is PreflightMode.LIVE_PREVIEW
    assert (dialog.controller.rows, dialog.controller.cols) == (ROWS, COLS)
    assert dialog.launcher is None


def test_open_forwards_launcher(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    launcher = object()

    dialog = _open(editor, launcher=launcher)

    assert dialog.launcher is launcher


# -- fake-modal flow ------------------------------------------------------


def test_fake_modal_full_flow_commits_once_at_finish(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    dialog = _open(editor)
    controller = dialog.controller

    assert controller.current_step is SetupStep.PREFLIGHT
    assert dialog.press_next() is True  # layout
    controller.draft.set_physical_layout("iso")
    controller.draft.set_legend_pack("auto")
    assert dialog.press_next() is True  # optional keys
    controller.draft.put_slot_override("menu", {"visible": False})
    assert dialog.press_next() is True  # calibration (valid keymap skips)
    assert dialog.press_next() is True  # overlay
    controller.draft.set_layout_tweak("dx", 1.0)
    assert dialog.press_next() is True  # review
    assert controller.current_step is SetupStep.REVIEW

    assert profiles.calls == []
    assert editor.commits == 0

    result = dialog.press_finish(profiles)

    assert result.ok is True
    assert dialog.finished == [True]
    assert dialog.alive is False
    assert editor._physical_layout == "iso"
    menu_slot = real_profiles.slot_id_for_key_id("iso", "menu") or "menu"
    assert editor.layout_slot_overrides.get(menu_slot, {}).get("visible") is False
    assert editor.layout_tweaks["dx"] == 1.0
    assert editor.commits == 0  # config-only snapshot: no hardware apply
    kinds = [call[0] for call in profiles.calls]
    assert kinds == ["save_keymap", "save_layout_global", "save_layout_per_key", "save_layout_slots"]


def test_fake_modal_cancel_discards_draft_with_zero_writes(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    dialog = _open(editor)

    assert dialog.press_next() is True
    dialog.controller.draft.set_physical_layout("iso")
    dialog.controller.draft.set_keymap(dict(OTHER_KEYMAP))
    assert dialog.press_cancel() is True

    assert profiles.calls == []
    assert editor.config.batches == 0
    assert editor._physical_layout == "ansi"
    assert editor.keymap == VALID_KEYMAP


def test_fake_modal_cancel_blocked_while_child_runs(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles()
    dialog = _open(editor)
    session_path = create_guided_session_file(
        dialog.controller.draft, rows=dialog.controller.rows, cols=dialog.controller.cols
    )
    try:
        dialog.controller.note_child_started(session_path)

        assert dialog.press_cancel() is False
        assert dialog.alive is True
        assert profiles.calls == []
    finally:
        dialog.controller.note_child_finished()
        integration.cleanup_guided_session(session_path)

    assert dialog.press_cancel() is True


def test_fake_modal_failed_finish_keeps_modal_open(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    profiles = FakeProfiles(fail_on="save_layout_global")
    dialog = _open(editor)
    while dialog.controller.current_step is not SetupStep.REVIEW:
        assert dialog.press_next() is True

    result = dialog.press_finish(profiles)

    assert result.ok is False
    assert result.rolled_back is True
    assert dialog.finished == [False]
    assert dialog.alive is True  # stays open for retry
    assert editor._physical_layout == "ansi"


def test_fake_modal_calibration_gate_end_to_end(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.keymap = {}
    dialog = _open(editor)
    while dialog.controller.current_step is not SetupStep.CALIBRATION:
        assert dialog.press_next() is True

    assert dialog.press_next() is False  # invalid keymap cannot advance

    dialog.controller.draft.set_keymap(dict(VALID_KEYMAP))
    assert dialog.press_next() is True  # explicit skip now permitted


def test_open_never_probes_hardware(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    calls: list[str] = []

    class ExplodingHardware:
        def __getattr__(self, name: str) -> Any:
            calls.append(name)
            raise AssertionError("must not touch hardware module")

    dialog = _open(editor, env=_snapshot_env(per_key=True), launcher=None, hardware_module=ExplodingHardware())

    assert dialog.controller.live is True
    assert calls == []


def test_live_only_with_valid_tray_snapshot_matrix(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    live_env = _snapshot_env(per_key=True)
    dark_env = _snapshot_env(per_key=False)

    live = resolve_setup_preflight(editor, env=live_env, hardware_module=FakeHardwareModule(None))
    dark = resolve_setup_preflight(editor, env=dark_env, hardware_module=FakeHardwareModule(FakeBackend()))

    assert live.mode is PreflightMode.LIVE_PREVIEW
    assert dark.mode is PreflightMode.CONFIG_ONLY
    assert "unavailable" in dark.message


def test_tray_payload_serializer_shape() -> None:
    payload = build_perkey_preflight_payload(
        backend_caps=_per_key_caps(), backend_name="Fake Backend", dimensions=(ROWS, COLS)
    )
    raw = json.dumps(payload)

    assert json.loads(raw)["per_key"] is True
    assert json.loads(raw)["dimensions"] == [ROWS, COLS]


def test_poll_error_keeps_child_and_session_for_retry(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    controller = _open(editor, env=_snapshot_env(per_key=True)).controller
    session_path = create_guided_session_file(controller.draft, rows=ROWS, cols=COLS)
    controller.note_child_started(session_path)

    class _PollErrorProcess:
        def poll(self) -> int | None:
            raise OSError("transient poll error")

    wizard = object.__new__(GuidedSetupWizard)
    wizard.editor = editor
    wizard.controller = controller
    wizard._child_process = _PollErrorProcess()
    scheduled: list[object] = []
    wizard._after = lambda delay, callback: scheduled.append((delay, callback))  # type: ignore[method-assign]

    wizard._poll_child()

    assert controller.child_running is True
    assert controller.session_path == session_path
    assert session_path.exists()
    assert len(scheduled) == 1
    controller.note_child_finished()
    integration.cleanup_guided_session(session_path)
