"""Shared main-window shortcut bindings (UX-08)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class _Bindable(Protocol):
    def bind(self, sequence: str, func: Callable[[object], object], add: str | None = None) -> object: ...


def install_window_bindings(
    root: object,
    *,
    on_close: Callable[[], object],
    on_save: Callable[[], object] | None = None,
    close_on_escape: bool = True,
) -> None:
    """Install shared main-window shortcuts on a Tk toplevel/root.

    Binds ``<Control-w>`` (and optionally ``<Escape>``) to ``on_close`` and
    optionally ``<Control-s>`` to ``on_save``.  Each binding uses ``add='+'``
    and returns ``'break'`` so the event does not propagate further.
    """

    bindable = cast(_Bindable, root)

    def _on_close(event: object) -> object:
        on_close()
        return "break"

    bindable.bind("<Control-w>", _on_close, add="+")
    if close_on_escape:
        bindable.bind("<Escape>", _on_close, add="+")
    if on_save is not None:

        def _on_save(event: object) -> object:
            on_save()
            return "break"

        bindable.bind("<Control-s>", _on_save, add="+")
