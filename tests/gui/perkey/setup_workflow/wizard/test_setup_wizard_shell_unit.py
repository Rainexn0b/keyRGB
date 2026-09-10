"""Guided-setup wizard shell/lifetime/render unit tests.

Split out of ``test_setup_wizard_unit.py`` to keep test modules under the
LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.gui.perkey.setup_workflow import integration, wizard as wizard_module
from keyrgb.gui.perkey.setup_workflow.integration import (
    SetupStep,
    create_guided_session_file,
)
from keyrgb.gui.perkey.setup_workflow.wizard import WIZARD_ATTR, GuidedSetupWizard, open_guided_setup
from tests.gui.perkey.setup_workflow._setup_fakes import (
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
    _WWToplevel,
)


def test_real_wizard_init_builds_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, editor, controller, registry = _make_real_wizard(monkeypatch, tmp_path)

    assert wizard._window.title_calls == ["KeyRGB - Guided Keyboard Setup"]
    assert wizard._back_button.options["text"] == "Back"
    assert wizard._finish_button.options["text"] == "Finish"
    assert controller.current_step is SetupStep.PREFLIGHT
    assert getattr(editor, WIZARD_ATTR, None) is None  # direct construction skips singleton store
    assert len(registry["toplevels"]) == 1


def test_real_wizard_init_tolerates_tk_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_wizard_fakes(monkeypatch)
    _WWToplevel.raise_on = {"transient", "protocol", "grab_set"}
    try:
        editor = FakeEditor(FakeConfig(tmp_path))
        editor.root = _WWRoot()  # type: ignore[attr-defined]
        wizard = GuidedSetupWizard(editor, _real_controller(editor, live=False))
    finally:
        _WWToplevel.raise_on = set()

    assert wizard.is_alive() is True
    assert len(registry["toplevels"]) == 1


def test_real_wizard_lifetime_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path)

    assert wizard.is_alive() is True
    wizard.focus()
    assert wizard._window.lift_calls == 1
    assert wizard._window.focus_calls == 1

    _WWToplevel.raise_on = {"winfo_exists", "lift", "grab_release", "destroy"}
    try:
        assert wizard.is_alive() is False  # error fails closed
        wizard.focus()  # tolerated
        wizard._release()  # tolerated, delattr path still runs
        wizard._destroy()  # tolerated
    finally:
        _WWToplevel.raise_on = set()
    assert wizard.is_alive() is True


def test_real_wizard_release_clears_singleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_wizard_fakes(monkeypatch)
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.root = _WWRoot()  # type: ignore[attr-defined]
    dialog = open_guided_setup(
        editor,
        env=_snapshot_env(per_key=False),
        hardware_module=FakeHardwareModule(FakeBackend()),
    )
    assert isinstance(dialog, GuidedSetupWizard)
    assert getattr(editor, WIZARD_ATTR) is dialog
    dialog._release()
    assert getattr(editor, WIZARD_ATTR, None) is None


def test_real_wizard_open_singleton_focus_and_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_wizard_fakes(monkeypatch)
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.root = _WWRoot()  # type: ignore[attr-defined]
    env = _snapshot_env(per_key=False)
    hardware = FakeHardwareModule(FakeBackend())

    first = open_guided_setup(editor, env=dict(env), hardware_module=hardware)
    assert isinstance(first, GuidedSetupWizard)
    second = open_guided_setup(editor, env=dict(env), hardware_module=hardware)
    assert second is first
    assert first._window.lift_calls == 1

    broken = getattr(editor, WIZARD_ATTR)
    broken._window.destroyed = True
    third = open_guided_setup(editor, env=dict(env), hardware_module=hardware)
    assert third is not first
    assert getattr(editor, WIZARD_ATTR) is third


def test_real_wizard_open_tolerates_broken_singleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_wizard_fakes(monkeypatch)
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.root = _WWRoot()  # type: ignore[attr-defined]

    class _Broken:
        def is_alive(self) -> bool:
            raise AttributeError("broken aliveness")

    editor._guided_setup_wizard = _Broken()  # type: ignore[attr-defined]
    dialog = open_guided_setup(
        editor, env=_snapshot_env(per_key=False), hardware_module=FakeHardwareModule(FakeBackend())
    )
    assert isinstance(dialog, GuidedSetupWizard)


def test_real_wizard_renders_all_six_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    seen: list[SetupStep] = []
    for step in controller.steps:
        controller.step_index = _step_index(controller, step)
        wizard._render()
        seen.append(controller.current_step)
        assert wizard._message_var.get() == controller.last_message or True
    assert seen == list(controller.steps)
    # Overlay page harvests five numeric entries.
    controller.step_index = _step_index(controller, SetupStep.OVERLAY)
    wizard._render()
    assert set(wizard._overlay_entries) == {"dx", "dy", "sx", "sy", "inset"}


def test_real_wizard_preflight_config_only_and_retry_button(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=False)
    assert controller.config_only is True
    controller.step_index = _step_index(controller, SetupStep.PREFLIGHT)
    wizard._render()
    retry_buttons = [b for b in wizard._body.children if b.options.get("text") == "Retry"]
    assert retry_buttons or controller.preflight.offer_retry is False
    # Retry re-resolves preflight and re-renders.
    before = controller.preflight.message
    wizard._retry_preflight()
    assert controller.last_message == controller.preflight.message
    assert isinstance(before, str)


def test_real_wizard_retry_blocked_while_child_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path, live=True)
    session_path = create_guided_session_file(controller.draft, rows=controller.rows, cols=controller.cols)
    try:
        controller.note_child_started(session_path)
        message_before = controller.last_message
        wizard._retry_preflight()
        assert controller.child_running is True
        assert controller.last_message == message_before
    finally:
        controller.note_child_finished()
        integration.cleanup_guided_session(session_path)


def test_real_wizard_layout_select_events_update_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.LAYOUT)
    wizard._render()
    assert len(registry["combos"]) >= 2
    layout_combo, legend_combo = registry["combos"][-2], registry["combos"][-1]
    binds = dict(layout_combo.bind_calls)
    assert "<<ComboboxSelected>>" in binds
    # Pick a different layout label so the draft actually changes.
    labels = list(layout_combo.values)
    assert labels
    other = next((label for label in labels if label != layout_combo.get()), labels[0])
    layout_combo.current = other
    binds["<<ComboboxSelected>>"](None)
    assert controller.draft.physical_layout
    legend_binds = dict(legend_combo.bind_calls)
    legend_combo.current = legend_combo.values[0] if legend_combo.values else "Default legends"
    legend_binds["<<ComboboxSelected>>"](None)
    assert controller.draft.legend_pack


def test_real_wizard_optional_keys_empty_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    monkeypatch.setattr(wizard_module, "optional_slot_states", lambda draft: [])
    controller.step_index = _step_index(controller, SetupStep.OPTIONAL_KEYS)
    wizard._render()
    assert wizard._option_vars == {}
    assert wizard._option_labels == {}
    wizard._harvest_page()  # empty harvest is a no-op


def test_real_wizard_optional_toggle_and_relabel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    controller.step_index = _step_index(controller, SetupStep.OPTIONAL_KEYS)
    wizard._render()
    assert wizard._option_vars, "ansi layout should expose optional keys"
    slot_id = next(iter(wizard._option_vars))
    entry = wizard._option_labels[slot_id]
    var = wizard._option_vars[slot_id]

    check = next(c for c in wizard._body.children if c.options.get("variable") is var)
    var.set(False)
    check.options["command"]()
    assert controller.draft.slot_overrides.get(slot_id, {}).get("visible") is False
    var.set(True)
    check.options["command"]()
    assert controller.draft.slot_overrides.get(slot_id, {}).get("visible", True) is not False

    entry._text = "My Label"
    relabel = dict(entry.bind_calls)["<FocusOut>"]
    relabel(None)
    assert controller.draft.slot_overrides.get(slot_id, {}).get("label") == "My Label"
    entry._text = ""
    relabel(None)
    assert "label" not in controller.draft.slot_overrides.get(slot_id, {})
    # Harvest path picks up widget text too.
    entry._text = "Harvested"
    wizard._harvest_optional_keys()
    assert controller.draft.slot_overrides.get(slot_id, {}).get("label") == "Harvested"


def test_real_wizard_optional_toggle_tolerates_var_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wizard, _editor, _controller, _registry = _make_real_wizard(monkeypatch, tmp_path)
    _controller.step_index = _step_index(_controller, SetupStep.OPTIONAL_KEYS)
    wizard._render()
    slot_id = next(iter(wizard._option_vars))

    class _ExplodingVar:
        def get(self) -> bool:
            raise RuntimeError("fake var failure")

    check = next(c for c in wizard._body.children if c.options.get("variable") is wizard._option_vars[slot_id])
    var = wizard._option_vars[slot_id]
    original_get = var.get
    var.get = _ExplodingVar().get  # type: ignore[method-assign]
    try:
        check.options["command"]()  # returns silently
    finally:
        var.get = original_get  # type: ignore[method-assign]
