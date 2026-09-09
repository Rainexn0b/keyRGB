"""Exception transparency for the responsive two-column helper."""

from __future__ import annotations

from tkinter import TclError

import pytest

from keyrgb.gui.perkey.ui.responsive_columns import (
    WIDE_THRESHOLD_PX,
    ResponsiveEntry,
    install_responsive_columns,
)

_WIDE = {"row": 0, "column": 0, "sticky": "nsew"}
_NARROW = {"row": 0, "column": 0, "columnspan": 2, "sticky": "nsew"}


class _FakeContainer:
    def __init__(self, width: int | Exception = WIDE_THRESHOLD_PX) -> None:
        self.width = width
        self.bind_calls: list[tuple[str, object, object | None]] = []
        self.bind_error: Exception | None = None

    def winfo_width(self) -> int:
        width = self.width
        if isinstance(width, Exception):
            raise width
        return int(width)

    def bind(self, event: str, callback: object, add: object | None = None) -> str:
        if self.bind_error is not None:
            raise self.bind_error
        self.bind_calls.append((event, callback, add))
        return "bound"


class _FakeWidget:
    def __init__(self, grid_error: Exception | None = None) -> None:
        self.grid_calls: list[dict[str, object]] = []
        self.grid_error = grid_error

    def grid(self, **kwargs: object) -> None:
        if self.grid_error is not None:
            raise self.grid_error
        self.grid_calls.append(dict(kwargs))


def _entry(widget: _FakeWidget) -> ResponsiveEntry:
    return ResponsiveEntry(widget=widget, wide=dict(_WIDE), narrow=dict(_NARROW))


@pytest.mark.parametrize("error", [RuntimeError("destroyed"), TclError("destroyed")])
def test_width_and_bind_boundary_errors_are_nonfatal(error: Exception) -> None:
    container = _FakeContainer(width=error)
    container.bind_error = error
    widget = _FakeWidget()

    sync = install_responsive_columns(container, [_entry(widget)])

    assert container.bind_calls == []
    sync(None)
    assert widget.grid_calls == []

    # The helper survives the boundary failure: a later valid width still
    # drives a single genuine transition.
    container.width = 500
    sync(None)
    assert widget.grid_calls == [dict(_NARROW)]


def test_unexpected_width_errors_propagate() -> None:
    container = _FakeContainer(width=AssertionError("boom"))
    widget = _FakeWidget()
    sync = install_responsive_columns(container, [_entry(widget)])

    with pytest.raises(AssertionError, match="boom"):
        sync(None)

    assert widget.grid_calls == []


@pytest.mark.parametrize("error", [RuntimeError("bad placement"), TclError("bad placement")])
def test_grid_errors_propagate_and_leave_transition_pending(error: Exception) -> None:
    container = _FakeContainer(width=500)
    widget = _FakeWidget(grid_error=error)
    sync = install_responsive_columns(container, [_entry(widget)])

    with pytest.raises(type(error), match="bad placement"):
        sync(None)

    # A failed transition is not marked complete: after the widget recovers,
    # later Configure traffic can finish the requested layout.
    widget.grid_error = None
    sync(None)
    assert widget.grid_calls == [dict(_NARROW)]


def test_threshold_boundary_is_wide() -> None:
    container = _FakeContainer(width=500)
    widget = _FakeWidget()
    sync = install_responsive_columns(container, [_entry(widget)])

    assert container.bind_calls[0][0] == "<Configure>"
    assert container.bind_calls[0][1] is sync

    sync(None)
    assert widget.grid_calls == [dict(_NARROW)]

    container.width = WIDE_THRESHOLD_PX - 1
    sync(None)
    assert widget.grid_calls == [dict(_NARROW)]

    container.width = WIDE_THRESHOLD_PX
    sync(None)
    assert widget.grid_calls[-1] == dict(_WIDE)
