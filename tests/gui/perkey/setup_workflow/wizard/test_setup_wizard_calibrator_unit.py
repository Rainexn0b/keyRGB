"""Guided-setup wizard calibrator-launch and poll-path unit tests.

Split out of ``test_setup_wizard_unit.py`` to keep test modules under the
LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from keyrgb.gui.perkey.setup_workflow import integration, wizard as wizard_module
from keyrgb.gui.perkey.setup_workflow.integration import (
    SetupStep,
    create_guided_session_file,
)
from keyrgb.gui.perkey.setup_workflow.wizard import WIZARD_ATTR, GuidedSetupWizard, open_guided_setup
from tests.gui.perkey.setup_workflow._setup_fakes import (
    VALID_KEYMAP,
    FakeBackend,
    FakeConfig,
    FakeEditor,
    FakeHardwareModule,
    _snapshot_env,
)
from tests.gui.perkey.setup_workflow._setup_wizard_fakes import (
    _install_wizard_fakes,
    _make_real_wizard,
    _real_controller,
    _step_index,
    _WWRoot,
)


def test_real_wizard_calibration_launch_disabled_config_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, registry = _make_real_wizard(monkeypatch, tmp_path, live=False)
    controller.step_index = _step_index(controller, SetupStep.CALIBRATION)
    before = len(registry["buttons"])
    wizard._render()
    launch = next(b for b in registry["buttons"][before:] if b.options.get("text") == "Launch guided calibrator")
    assert launch.options.get("state") == "disabled"
    wizard._on_launch_calibrator()
    assert "config-only" in wizard._message_var.get()


def test_real_wizard_launch_success_and_poll_adopt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from keyrgb.gui.calibrator.guided import write_guided_result

    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    controller.step_index = _step_index(controller, SetupStep.CALIBRATION)
    wizard._render()

    class _FakeProc:
        def __init__(self) -> None:
            self.calls = 0

        def poll(self) -> int | None:
            self.calls += 1
            return None if self.calls == 1 else 0

    proc = _FakeProc()
    wizard._launcher = lambda session_path: proc  # type: ignore[assignment]
    wizard._on_launch_calibrator()
    assert controller.child_running is True
    assert wizard._child_process is proc
    session_path = controller.session_path
    assert session_path is not None
    root = wizard._editor_root()
    assert isinstance(root, _WWRoot)
    assert root.after_calls, "launch schedules a poll"

    wizard._poll_child()  # still running -> reschedule
    assert controller.child_running is True

    write_guided_result(session_path, {"a": ((0, 0),), "b": ((1, 2),)}, physical_layout="ansi")
    wizard._poll_child()  # exited -> adopt + re-render
    assert controller.child_running is False
    assert len(controller.draft.keymap) == 2
    assert "adopted" in wizard._message_var.get().lower() or "You may continue" in wizard._message_var.get()


def test_real_wizard_launch_session_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    monkeypatch.setattr(
        wizard_module, "create_guided_session_file", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk"))
    )
    wizard._on_launch_calibrator()
    assert "Could not prepare" in wizard._message_var.get()


def test_real_wizard_launch_launcher_failure_cleans_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    cleaned: list[Any] = []
    monkeypatch.setattr(wizard_module, "cleanup_guided_session", lambda path: cleaned.append(path))

    def _boom_launcher(path: Any) -> Any:
        raise OSError("fake launch failure")

    wizard._launcher = _boom_launcher  # type: ignore[assignment]
    wizard._on_launch_calibrator()
    assert "Could not launch" in wizard._message_var.get()
    assert cleaned, "failed launch cleans the temp session"
    assert controller.child_running is False


def test_real_wizard_poll_no_child_returns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    wizard._child_process = None
    root = wizard._editor_root()
    assert isinstance(root, _WWRoot)
    calls_before = len(root.after_calls)
    wizard._poll_child()
    assert len(root.after_calls) == calls_before


def test_real_wizard_poll_error_reschedules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    try:
        controller.note_child_started(session_path)

        class _PollError:
            def poll(self) -> int | None:
                raise OSError("transient")

        wizard._child_process = _PollError()
        root = wizard._editor_root()
        assert isinstance(root, _WWRoot)
        calls_before = len(root.after_calls)
        wizard._poll_child()
        assert len(root.after_calls) == calls_before + 1
        assert controller.child_running is True
    finally:
        controller.note_child_finished()
        integration.cleanup_guided_session(session_path)


def test_real_wizard_finish_child_without_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    controller.note_child_started(session_path)  # no result written
    wizard._child_process = SimpleNamespace(poll=lambda: 0)
    wizard._poll_child()
    assert controller.child_running is False
    assert "without a usable result" in wizard._message_var.get()


def test_real_wizard_resolve_launcher_default_and_cleanup_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    launcher = wizard._resolve_launcher()
    assert callable(launcher)
    controller.session_path = tmp_path / "session.json"  # type: ignore[assignment]
    wizard._cleanup_session_reference()
    assert controller.session_path is None


def test_real_wizard_cleanup_session_marks_finished(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    controller.note_child_started(session_path)
    wizard._child_process = SimpleNamespace(poll=lambda: None)
    wizard._poll_job = object()
    wizard._cleanup_session()
    assert controller.child_running is False
    assert wizard._child_process is None
    assert not session_path.exists()


def test_real_wizard_render_tolerates_child_destroy_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()

    class _ExplodingChild:
        def destroy(self) -> None:
            raise RuntimeError("fake destroy failure")

    wizard._body.children.append(_ExplodingChild())  # type: ignore[arg-type]
    wizard._render()  # destroy errors tolerated
    assert controller.current_step is SetupStep.REVIEW


def test_real_wizard_harvest_overlay_set_tweak_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.OVERLAY)
    wizard._render()
    monkeypatch.setattr(
        controller.draft, "set_layout_tweak", lambda name, value: (_ for _ in ()).throw(ValueError("bad tweak"))
    )
    wizard._overlay_entries["dx"]._text = "1.0"
    wizard._harvest_overlay()  # tweak errors skipped


def test_real_wizard_calibration_pages_cover_config_only_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=False)
    controller.step_index = _step_index(controller, SetupStep.CALIBRATION)
    controller.draft.set_keymap({})
    wizard._render()  # config-only + invalid branch
    controller.draft.set_keymap(dict(VALID_KEYMAP))
    wizard._render()  # config-only + valid branch
    assert wizard._message_var is not None


def test_real_wizard_review_page_and_layout_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.REVIEW)
    wizard._render()
    controller.draft.set_keymap({})
    wizard._render()  # invalid keymap line in review
    labels, id_to_label, label_to_id = wizard_module._layout_labels()
    assert labels and id_to_label and label_to_id


def test_real_wizard_open_tolerates_delete_and_store_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_wizard_fakes(monkeypatch)

    class _Broken:
        def is_alive(self) -> bool:
            raise AttributeError("broken aliveness")

    class _LockedEditor:
        def __init__(self, root: Any) -> None:
            object.__setattr__(self, "root", root)
            object.__setattr__(self, WIZARD_ATTR, _Broken())

        def __setattr__(self, name: str, value: Any) -> None:
            raise OSError("locked editor")

        def __delattr__(self, name: str) -> None:
            raise OSError("locked editor")

    editor = _LockedEditor(_WWRoot())
    dialog = open_guided_setup(
        editor,  # type: ignore[arg-type]
        env=_snapshot_env(per_key=False),
        hardware_module=FakeHardwareModule(FakeBackend()),
    )
    assert isinstance(dialog, GuidedSetupWizard)


def test_real_wizard_relabel_entry_and_override_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.OPTIONAL_KEYS)
    wizard._render()
    slot_id = next(iter(wizard._option_labels))
    entry = wizard._option_labels[slot_id]
    relabel = dict(entry.bind_calls)["<FocusOut>"]
    # Widget read errors are skipped.
    entry.fail_get = True
    relabel(None)
    entry.fail_get = False
    # Override persist errors are skipped.
    entry._text = "Persist Boom"
    monkeypatch.setattr(
        controller.draft, "put_slot_override", lambda slot, override: (_ for _ in ()).throw(ValueError("bad"))
    )
    relabel(None)
    # Harvest read errors are skipped.
    entry.fail_get = True
    wizard._harvest_optional_keys()
    entry.fail_get = False


def test_real_wizard_calibration_launch_disable_tolerates_button_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_wizard_fakes(monkeypatch)
    real_ttk = wizard_module.ttk

    class _ExplodingButton(real_ttk.Button):  # type: ignore[misc]
        def configure(self, **kwargs: Any) -> None:
            raise RuntimeError("fake button failure")

    namespace = SimpleNamespace(**vars(real_ttk))
    namespace.Button = _ExplodingButton
    monkeypatch.setattr(wizard_module, "ttk", namespace)
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.root = _WWRoot()  # type: ignore[attr-defined]
    controller = _real_controller(editor, live=False)
    wizard = GuidedSetupWizard(editor, controller)
    controller.step_index = _step_index(controller, SetupStep.CALIBRATION)
    wizard._render()  # disabled-configure failure tolerated
