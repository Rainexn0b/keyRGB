from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import TypeVar

import tkinter as tk


T = TypeVar("T")


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
        root.after(0, lambda: on_done(result))

    if delay_ms and delay_ms > 0:
        root.after(delay_ms, lambda: Thread(target=worker, daemon=True).start())
    else:
        Thread(target=worker, daemon=True).start()
