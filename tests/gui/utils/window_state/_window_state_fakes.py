from __future__ import annotations

"""Shared fakes for window-state tests."""

import hashlib
from pathlib import Path


class _FakeRoot:
    """Minimal duck-typed Tk root for tracker tests (no Tkinter import)."""

    def __init__(self, width=880, height=840, x=100, y=80, screen=(2560, 1600)):
        self._width = width
        self._height = height
        self._x = x
        self._y = y
        self._screen = screen
        self.bindings: list[tuple[str, object]] = []
        self.scheduled: list[tuple[int, object]] = []
        self.cancelled: list[object] = []
        self.applied: list[str] = []
        self._next_after_id = 0

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))

    def after(self, delay_ms, callback):
        self._next_after_id += 1
        token = f"after-{self._next_after_id}"
        self.scheduled.append((int(delay_ms), callback, token))
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)
        self.scheduled = [entry for entry in self.scheduled if entry[2] != token]

    def fire_pending(self):
        pending = [entry[1] for entry in self.scheduled]
        self.scheduled.clear()
        for callback in pending:
            callback()

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_x(self):
        return self._x

    def winfo_y(self):
        return self._y

    def winfo_screenwidth(self):
        return self._screen[0]

    def winfo_screenheight(self):
        return self._screen[1]

    def geometry(self, value):
        self.applied.append(value)


def _config_digest_and_mtime(path: Path) -> tuple[str | None, float | None]:
    if not path.exists():
        return None, None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, path.stat().st_mtime_ns
