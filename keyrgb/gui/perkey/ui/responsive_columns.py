"""Shared responsive two-column helper for per-key notebook tabs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from tkinter import TclError
from typing import Literal, Protocol

WIDE_THRESHOLD_PX = 900

_TK_ERRORS = (RuntimeError, TclError)

GridOptions = dict[str, object]
ResponsiveMode = Literal["wide", "narrow"]
ResponsiveCallback = Callable[[object | None], None]


class ResponsiveWidget(Protocol):
    def grid(self, **kwargs: object) -> None: ...


class ResponsiveContainer(Protocol):
    def winfo_width(self) -> int: ...

    def bind(self, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class ResponsiveEntry:
    """One tab section with its wide and narrow grid placements.

    Conditional panels (lighting areas) additionally provide ``is_hidden``
    and ``record_hidden``: while hidden the helper updates their saved
    placement without calling ``grid()``, so they stay hidden and a later
    re-show cannot overlap the other column.
    """

    widget: ResponsiveWidget
    wide: Mapping[str, object]
    narrow: Mapping[str, object]
    is_hidden: Callable[[], bool] | None = None
    record_hidden: Callable[[Mapping[str, object]], None] | None = None


def install_responsive_columns(
    container: ResponsiveContainer,
    entries: Sequence[ResponsiveEntry],
    *,
    threshold: int = WIDE_THRESHOLD_PX,
    initial_mode: ResponsiveMode = "wide",
) -> ResponsiveCallback:
    """Re-grid tab sections side-by-side when wide, stacked when narrow.

    The caller grids everything with the wide options up front; this helper
    only re-grids on a genuine narrow/wide transition so ``<Configure>``
    traffic cannot oscillate or issue redundant grids.
    """
    snapshot = tuple(
        ResponsiveEntry(
            widget=entry.widget,
            wide=dict(entry.wide),
            narrow=dict(entry.narrow),
            is_hidden=entry.is_hidden,
            record_hidden=entry.record_hidden,
        )
        for entry in entries
    )
    current_mode = initial_mode

    def sync(_event: object | None = None) -> None:
        nonlocal current_mode
        try:
            width = int(container.winfo_width())
        except _TK_ERRORS:
            return
        mode: ResponsiveMode = "wide" if width >= threshold else "narrow"
        if mode == current_mode:
            return
        for entry in snapshot:
            target = entry.wide if mode == "wide" else entry.narrow
            if entry.is_hidden is not None and entry.is_hidden():
                if entry.record_hidden is not None:
                    entry.record_hidden(target)
                continue
            # Static placement errors propagate: a bad grid call is a bug,
            # not a lifecycle event. Only width/bind boundaries are guarded.
            entry.widget.grid(**dict(target))
        current_mode = mode

    try:
        container.bind("<Configure>", sync, add=True)
    except _TK_ERRORS:
        pass
    return sync


__all__ = [
    "WIDE_THRESHOLD_PX",
    "GridOptions",
    "ResponsiveCallback",
    "ResponsiveContainer",
    "ResponsiveEntry",
    "ResponsiveMode",
    "ResponsiveWidget",
    "install_responsive_columns",
]
