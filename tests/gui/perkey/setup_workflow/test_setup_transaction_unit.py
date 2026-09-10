from __future__ import annotations

import copy

import pytest

from keyrgb.gui.perkey.setup_workflow.model import SetupSource, cancel_setup, draft_from_source
from keyrgb.gui.perkey.setup_workflow.transaction import (
    DEFAULT_EXPECTED_ERRORS,
    SetupCommitCallbacks,
    finish_setup,
)


class _Recorder:
    def __init__(self, *, fail_at: str | None = None, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.fail_at = fail_at
        self.error = error or OSError("disk full")
        self.restored = []

    def _maybe_fail(self, stage: str) -> None:
        self.calls.append(stage)
        if self.fail_at == stage:
            raise self.error

    def apply_draft(self, draft) -> None:
        self._maybe_fail("apply_draft")

    def persist(self, draft) -> None:
        self._maybe_fail("persist")

    def apply_hardware(self, draft) -> None:
        self._maybe_fail("apply_hardware")

    def restore_original(self, snapshot) -> None:
        self.restored.append(snapshot)


def _callbacks(rec: _Recorder, *, with_hardware: bool = True) -> SetupCommitCallbacks:
    return SetupCommitCallbacks(
        apply_draft=rec.apply_draft,
        persist=rec.persist,
        restore_original=rec.restore_original,
        apply_hardware=rec.apply_hardware if with_hardware else None,
    )


def test_finish_success_runs_explicit_ordering() -> None:
    rec = _Recorder()
    draft = draft_from_source(SetupSource(physical_layout="iso"))
    result = finish_setup(draft, _callbacks(rec))

    assert result.ok is True
    assert result.stage == "committed"
    assert rec.calls == ["apply_draft", "persist", "apply_hardware"]
    assert rec.restored == []


def test_finish_without_hardware_callback_still_commits() -> None:
    rec = _Recorder()
    draft = draft_from_source(SetupSource())
    result = finish_setup(draft, _callbacks(rec, with_hardware=False))

    assert result.ok is True
    assert rec.calls == ["apply_draft", "persist"]


@pytest.mark.parametrize(
    ("fail_at", "error", "stage"),
    [
        ("apply_draft", RuntimeError("no device"), "apply_draft"),
        ("persist", OSError("disk full"), "persist"),
        ("apply_hardware", ValueError("bad push"), "apply_hardware"),
    ],
)
def test_finish_failure_at_each_stage_rolls_back(fail_at: str, error: Exception, stage: str) -> None:
    rec = _Recorder(fail_at=fail_at, error=error)
    draft = draft_from_source(SetupSource(physical_layout="iso"))
    draft.set_physical_layout("ansi")

    result = finish_setup(draft, _callbacks(rec))

    assert result.ok is False
    assert result.stage == stage
    assert result.rolled_back is True
    assert result.error is error
    assert result.restore_error is None
    # Restore receives a fresh deep copy; draft edits kept so workflow stays open.
    assert rec.restored == [draft.original]
    assert rec.restored[0] is not draft.original
    assert draft.physical_layout == "ansi"


def test_finish_unexpected_exception_propagates_after_rollback() -> None:
    boom = KeyError("programmer bug")
    rec = _Recorder(fail_at="persist", error=boom)
    draft = draft_from_source(SetupSource())

    with pytest.raises(KeyError) as excinfo:
        finish_setup(draft, _callbacks(rec))

    assert excinfo.value is boom
    assert rec.restored == [draft.original]
    assert rec.restored[0] is not draft.original


def test_finish_rollback_failure_preserves_diagnostic_context() -> None:
    stage_error = OSError("disk full")
    restore_error = RuntimeError("config locked")

    def restore(snapshot) -> None:
        raise restore_error

    callbacks = SetupCommitCallbacks(
        apply_draft=lambda draft: None,
        persist=lambda draft: (_ for _ in ()).throw(stage_error),
        restore_original=restore,
    )
    draft = draft_from_source(SetupSource())

    result = finish_setup(draft, callbacks)

    assert result.ok is False
    assert result.stage == "persist"
    assert result.rolled_back is False
    assert result.error is stage_error
    assert result.restore_error is restore_error


def test_finish_unexpected_exception_with_failed_rollback_chains() -> None:
    boom = KeyError("programmer bug")
    restore_error = OSError("cannot restore")

    def restore(snapshot) -> None:
        raise restore_error

    callbacks = SetupCommitCallbacks(
        apply_draft=lambda draft: None,
        persist=lambda draft: (_ for _ in ()).throw(boom),
        restore_original=restore,
    )
    draft = draft_from_source(SetupSource())

    with pytest.raises(OSError) as excinfo:
        finish_setup(draft, callbacks)

    assert excinfo.value is restore_error
    assert excinfo.value.__cause__ is boom


def test_finish_custom_expected_errors_tuple() -> None:
    rec = _Recorder(fail_at="persist", error=KeyError("custom"))
    draft = draft_from_source(SetupSource())

    result = finish_setup(draft, _callbacks(rec), expected_errors=(KeyError,))
    assert result.ok is False
    assert result.stage == "persist"
    assert result.rolled_back is True


def test_finish_rejects_bad_arguments() -> None:
    draft = draft_from_source(SetupSource())
    rec = _Recorder()
    with pytest.raises(TypeError):
        finish_setup(draft, object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        finish_setup(draft, _callbacks(rec), expected_errors=())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        finish_setup(draft, _callbacks(rec), expected_errors=(ValueError, int))  # type: ignore[arg-type]


@pytest.mark.parametrize("forbidden", [BaseException, KeyboardInterrupt, SystemExit])
def test_finish_boundary_cannot_catch_interpreter_exits(forbidden) -> None:
    draft = draft_from_source(SetupSource())
    with pytest.raises(TypeError):
        finish_setup(draft, _callbacks(_Recorder()), expected_errors=(forbidden,))


def test_default_expected_errors_are_exception_subclasses() -> None:
    assert DEFAULT_EXPECTED_ERRORS
    assert all(issubclass(item, Exception) for item in DEFAULT_EXPECTED_ERRORS)
    assert not any(issubclass(item, (KeyboardInterrupt, SystemExit)) for item in DEFAULT_EXPECTED_ERRORS)


def test_repeated_rollbacks_and_cancel_use_pristine_original() -> None:
    source = SetupSource(
        physical_layout="iso",
        slot_overrides={"slot-01": {"label": "Esc", "meta": {"depth": 1}}},
        keymap={"slot-01": ((0, 0),)},
    )
    draft = draft_from_source(source)
    # Late source mutation must not reach the stored original.
    source.slot_overrides["slot-01"]["label"] = "MUTATED-SOURCE"
    # Draft edits must not reach the stored original either.
    draft.slot_overrides["slot-01"]["label"] = "MUTATED-DRAFT"

    received: list = []

    def hostile_restore(snapshot) -> None:
        # Record the as-received state before mutating it.
        received.append(copy.deepcopy({"keymap": snapshot.keymap, "slots": snapshot.slot_overrides}))
        snapshot.keymap["slot-01"] = ((9, 9),)
        snapshot.slot_overrides["slot-01"]["label"] = "MUTATED-RESTORE"
        snapshot.slot_overrides["slot-01"]["meta"]["depth"] = 99

    def fail(_draft) -> None:
        raise OSError("disk full")

    callbacks = SetupCommitCallbacks(
        apply_draft=lambda _draft: None,
        persist=fail,
        restore_original=hostile_restore,
    )

    first = finish_setup(draft, callbacks)
    second = finish_setup(draft, callbacks)
    assert first.rolled_back is True
    assert second.rolled_back is True
    # Each rollback attempt received an independent, pristine deep copy.
    assert len(received) == 2
    assert received[0] is not received[1]
    assert received[0] == received[1] == {"keymap": draft.original.keymap, "slots": draft.original.slot_overrides}
    # The stored original is still pristine for cancel, and cancel copies too.
    cancelled = cancel_setup(draft)
    assert cancelled == draft.original
    assert cancelled is not draft.original
    cancelled.keymap["slot-01"] = ((8, 8),)
    assert cancel_setup(draft) == draft.original
    assert draft.original.slot_overrides == {"slot-01": {"label": "Esc", "meta": {"depth": 1}}}
    assert draft.original.keymap == {"slot-01": ((0, 0),)}
