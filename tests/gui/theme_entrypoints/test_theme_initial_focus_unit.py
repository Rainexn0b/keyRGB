from __future__ import annotations

import logging

import pytest

from keyrgb.gui.theme import focus as theme_focus


class _FakeTarget:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.focus_calls = 0

    def focus_set(self) -> None:
        self.focus_calls += 1
        if self._error is not None:
            raise self._error


class _FakeRoot:
    def __init__(
        self,
        *,
        focused: object = None,
        after_error: Exception | None = None,
        focus_error: Exception | None = None,
    ) -> None:
        self._focused = focused
        self._after_error = after_error
        self._focus_error = focus_error
        self.after_calls: list[tuple[int, object]] = []

    def after(self, delay_ms: int, callback: object) -> str:
        self.after_calls.append((delay_ms, callback))
        if self._after_error is not None:
            raise self._after_error
        return "after-id"

    def focus_get(self) -> object:
        if self._focus_error is not None:
            raise self._focus_error
        return self._focused


def _fire(root: _FakeRoot) -> None:
    assert len(root.after_calls) == 1
    callback = root.after_calls[0][1]
    assert callable(callback)
    callback()


def test_schedules_focus_with_default_delay_when_nothing_focused() -> None:
    root = _FakeRoot(focused=None)
    target = _FakeTarget()

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]

    assert [delay for delay, _ in root.after_calls] == [theme_focus.INITIAL_FOCUS_DELAY_MS]
    _fire(root)
    assert target.focus_calls == 1


def test_custom_delay_is_forwarded_to_after() -> None:
    root = _FakeRoot(focused=None)
    target = _FakeTarget()

    theme_focus.schedule_initial_focus(root, target, delay_ms=120)  # type: ignore[arg-type]

    assert [delay for delay, _ in root.after_calls] == [120]
    _fire(root)
    assert target.focus_calls == 1


def test_does_not_override_an_already_focused_child() -> None:
    already_focused = object()
    root = _FakeRoot(focused=already_focused)
    target = _FakeTarget()

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]
    _fire(root)

    assert target.focus_calls == 0


def test_replaces_root_only_focus_with_the_initial_control() -> None:
    root = _FakeRoot()
    root._focused = root
    target = _FakeTarget()

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]
    _fire(root)

    assert target.focus_calls == 1


def test_after_scheduling_failure_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    root = _FakeRoot(after_error=theme_focus.tk.TclError("torn down"))
    target = _FakeTarget()

    with caplog.at_level(logging.DEBUG, logger="keyrgb.gui.theme.focus"):
        theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]

    assert root.after_calls[0][0] == theme_focus.INITIAL_FOCUS_DELAY_MS
    assert target.focus_calls == 0
    assert any("could not be scheduled" in record.message for record in caplog.records)


def test_focus_check_failure_leaves_target_alone() -> None:
    root = _FakeRoot(focus_error=theme_focus.tk.TclError("window closed"))
    target = _FakeTarget()

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]
    _fire(root)

    assert target.focus_calls == 0


def test_focus_set_failure_is_swallowed() -> None:
    root = _FakeRoot(focused=None)
    target = _FakeTarget(error=theme_focus.tk.TclError("target gone"))

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]
    _fire(root)

    assert target.focus_calls == 1


def test_never_uses_force_or_grab() -> None:
    root = _FakeRoot(focused=None)
    target = _FakeTarget()

    assert not hasattr(root, "focus_force")
    assert not hasattr(root, "grab_set")
    assert not hasattr(target, "focus_force")
    assert not hasattr(target, "grab_set")

    theme_focus.schedule_initial_focus(root, target)  # type: ignore[arg-type]
    _fire(root)

    assert target.focus_calls == 1
