"""Guided-setup wizard navigation and finish-path unit tests.

Split out of ``test_setup_wizard_unit.py`` to keep test modules under the
LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from keyrgb.gui.perkey.setup_workflow import integration, wizard as wizard_module
from keyrgb.gui.perkey.setup_workflow.integration import (
    SetupStep,
    build_setup_commit_callbacks,
    create_guided_session_file,
    resolve_setup_preflight,
)
from tests.gui.perkey.setup_workflow._setup_fakes import (
    VALID_KEYMAP,
    FakeHardwareModule,
    FakeProfiles,
)
from tests.gui.perkey.setup_workflow._setup_wizard_fakes import (
    _make_real_wizard,
    _step_index,
    _WWRoot,
    _WWWidget,
)


def test_real_wizard_overlay_harvest_and_inset_clamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.OVERLAY)
    wizard._render()
    wizard._overlay_entries["dx"]._text = "1.5"
    wizard._overlay_entries["inset"]._text = "9.0"  # clamps to 0.20
    wizard._overlay_entries["dy"]._text = "not-a-number"  # skipped
    wizard._harvest_overlay()
    assert controller.draft.layout_tweaks["dx"] == 1.5
    assert controller.draft.layout_tweaks["inset"] == 0.20
    wizard._overlay_entries["inset"]._text = "-3.0"  # clamps to 0.0
    wizard._harvest_overlay()
    assert controller.draft.layout_tweaks["inset"] == 0.0
    # Entry read errors are skipped.
    wizard._overlay_entries["dx"]._text = "2.5"
    wizard._overlay_entries["dx"].fail_get = True
    wizard._harvest_overlay()
    assert controller.draft.layout_tweaks["dx"] == 1.5


def test_real_wizard_nav_buttons_harvest_and_move(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.OVERLAY)
    wizard._render()
    wizard._overlay_entries["dx"]._text = "2.0"
    wizard._on_next()
    assert controller.draft.layout_tweaks["dx"] == 2.0
    assert controller.current_step is SetupStep.REVIEW
    wizard._on_back()
    assert controller.current_step is SetupStep.OVERLAY


def test_real_wizard_refresh_nav_states(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    # First step: Back disabled, Finish disabled (not last).
    controller.step_index = 0
    wizard._render()
    assert wizard._back_button.options.get("state") == "disabled"
    assert wizard._finish_button.options.get("state") == "disabled"
    # Last step: Next disabled, Finish enabled.
    controller.step_index = len(controller.steps) - 1
    wizard._render()
    assert wizard._next_button.options.get("state") == "disabled"
    assert wizard._finish_button.options.get("state") != "disabled"
    # Child running: everything disabled.
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    try:
        controller.note_child_started(session_path)
        wizard._refresh_nav()
        for button in (
            wizard._back_button,
            wizard._next_button,
            wizard._cancel_button,
            wizard._finish_button,
        ):
            assert button.options.get("state") == "disabled"
    finally:
        controller.note_child_finished()
        integration.cleanup_guided_session(session_path)
    # Blocked preflight disables Next.
    controller.step_index = 0
    controller.preflight = resolve_setup_preflight(_editor, env={}, hardware_module=FakeHardwareModule(None))
    controller.preflight = controller.preflight  # keep shape; force blocked below
    from keyrgb.gui.perkey.setup_workflow.preflight import PreflightMode as _Mode

    if controller.preflight.mode is not _Mode.BLOCKED:
        import dataclasses as _dc

        controller.preflight = _dc.replace(controller.preflight, mode=_Mode.BLOCKED, message="blocked for test")
    wizard._refresh_nav()
    assert wizard._next_button.options.get("state") == "disabled"


def test_real_wizard_refresh_nav_tolerates_button_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)

    class _ExplodingButton(_WWWidget):
        def configure(self, **kwargs: Any) -> None:
            raise RuntimeError("fake configure failure")

    wizard._back_button = _ExplodingButton()  # type: ignore[assignment]
    controller.last_message = "hello"
    wizard._refresh_nav()  # all configure errors tolerated
    assert wizard._message_var.get() == "hello"


def test_real_wizard_after_and_stop_polling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    wizard._after(250, lambda: None)
    assert wizard._poll_job is not None
    wizard._stop_polling()
    assert wizard._poll_job is None
    wizard._stop_polling()  # no job: no-op
    root = wizard._editor_root()
    assert isinstance(root, _WWRoot)
    root.fail_after = True
    wizard._after(250, lambda: None)  # scheduling failure is logged, not raised
    wizard._poll_job = object()
    root.fail_cancel = True
    wizard._stop_polling()  # cancel failure tolerated
    assert wizard._poll_job is None


def test_real_wizard_set_message_tolerates_var_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path)

    class _ExplodingVar:
        def set(self, value: Any) -> None:
            raise RuntimeError("fake set failure")

    wizard._message_var = _ExplodingVar()  # type: ignore[assignment]
    wizard._set_message("hi")  # tolerated


def test_real_wizard_close_blocked_and_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    try:
        controller.note_child_started(session_path)
        wizard._on_close_request()
        assert wizard._window.destroyed is False
        assert "still running" in wizard._message_var.get()
        controller.note_child_finished()
    finally:
        integration.cleanup_guided_session(session_path)
    controller.last_message = "stale"
    wizard._on_close_request()
    assert wizard._window.destroyed is True
    assert controller.last_message == ""


def test_real_wizard_safe_status_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    calls: list[str] = []

    class _Label:
        def config(self, *, text: str) -> None:
            calls.append(text)

    editor.status_label = _Label()  # type: ignore[attr-defined]
    wizard._safe_status("hello-status")
    assert calls == ["hello-status"]

    import keyrgb.gui.perkey.ui.status as status_module

    monkeypatch.setattr(status_module, "set_status", lambda editor, message: (_ for _ in ()).throw(OSError("boom")))
    wizard._safe_status("tolerated")

    monkeypatch.setitem(sys.modules, "keyrgb.gui.perkey.ui.status", SimpleNamespace())
    wizard._safe_status("import failure tolerated")


def test_real_wizard_finish_gate_not_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = 0
    wizard._render()
    wizard._on_finish()
    assert wizard._message_var.get() == "Review every setup step before choosing Finish."
    assert wizard._window.destroyed is False


def test_real_wizard_finish_blocked_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    import dataclasses as _dc

    from keyrgb.gui.perkey.setup_workflow.preflight import PreflightMode as _Mode

    controller.preflight = _dc.replace(controller.preflight, mode=_Mode.BLOCKED, message="blocked finish")
    controller.draft.set_keymap(dict(VALID_KEYMAP))
    wizard._on_finish()
    assert wizard._message_var.get() == "blocked finish"
    assert wizard._window.destroyed is False


def test_real_wizard_finish_invalid_keymap_stays_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    controller.draft.set_keymap({})
    wizard._on_finish()
    assert "not ready" in wizard._message_var.get()
    assert wizard._window.destroyed is False


def test_real_wizard_finish_success_marks_saved_and_closes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    profiles = FakeProfiles()
    saved: list[bool] = []
    statuses: list[str] = []
    editor._mark_saved_snapshot = lambda: saved.append(True)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        wizard_module,
        "build_setup_commit_callbacks",
        lambda editor_arg, draft, config_only=False: build_setup_commit_callbacks(
            editor_arg, draft, config_only=config_only, profiles_module=profiles
        ),
    )
    monkeypatch.setattr(wizard, "_safe_status", lambda message: statuses.append(message))
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    wizard._on_finish()
    assert wizard._window.destroyed is True
    assert saved == [True]
    assert statuses == ["Guided setup complete"]
    assert [call[0] for call in profiles.calls] == [
        "save_keymap",
        "save_layout_global",
        "save_layout_per_key",
        "save_layout_slots",
    ]


def test_real_wizard_finish_success_tolerates_mark_saved_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    profiles = FakeProfiles()

    def _boom() -> None:
        raise OSError("fake marker failure")

    editor._mark_saved_snapshot = _boom  # type: ignore[attr-defined]
    monkeypatch.setattr(
        wizard_module,
        "build_setup_commit_callbacks",
        lambda editor_arg, draft, config_only=False: build_setup_commit_callbacks(
            editor_arg, draft, config_only=config_only, profiles_module=profiles
        ),
    )
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    wizard._on_finish()
    assert wizard._window.destroyed is True


def test_real_wizard_failed_finish_stays_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    profiles = FakeProfiles(fail_on="save_layout_global")
    monkeypatch.setattr(
        wizard_module,
        "build_setup_commit_callbacks",
        lambda editor_arg, draft, config_only=False: build_setup_commit_callbacks(
            editor_arg, draft, config_only=config_only, profiles_module=profiles
        ),
    )
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    wizard._on_finish()
    assert wizard._window.destroyed is False
    assert wizard._message_var.get() != ""
    assert editor._physical_layout == "ansi"  # rolled back


def test_real_wizard_finish_exception_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    profiles = FakeProfiles()
    monkeypatch.setattr(
        wizard_module,
        "build_setup_commit_callbacks",
        lambda editor_arg, draft, config_only=False: build_setup_commit_callbacks(
            editor_arg, draft, config_only=config_only, profiles_module=profiles
        ),
    )

    def _boom_finish(callbacks: Any) -> Any:
        raise OSError("boom")

    monkeypatch.setattr(controller, "finish", _boom_finish)
    wizard._on_finish()
    assert "could not finish safely" in wizard._message_var.get()
    assert wizard._window.destroyed is False
