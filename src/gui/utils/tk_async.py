from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import TypeVar

import tkinter as tk


T = TypeVar("T")
_TK_SCHEDULE_ERRORS = (RuntimeError, tk.TclError)


def _schedule_on_tk_thread(root: tk.Misc, callback: Callable[[], None], *, delay_ms: int = 0) -> bool:
    try:
        root.after(delay_ms, callback)
    except _TK_SCHEDULE_ERRORS:
        return False
    return True


def run_in_thread(
    root: tk.Misc,
    work: Callable[[], T],
    on_done: Callable[[T], None],
    *,
    delay_ms: int = 0,
) -> None:
    """Run work in a daemon thread and call on_done(result) on Tk's thread.

    This is a tiny utility to keep Tkinter UIs responsive while doing blocking work.
    """

    def worker() -> None:
        result = work()
        _schedule_on_tk_thread(root, lambda: on_done(result))

    if delay_ms and delay_ms > 0:
        _schedule_on_tk_thread(root, lambda: Thread(target=worker, daemon=True).start(), delay_ms=delay_ms)
    else:
        Thread(target=worker, daemon=True).start()
