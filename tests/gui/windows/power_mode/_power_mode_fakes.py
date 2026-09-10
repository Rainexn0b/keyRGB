"""Shared fakes for power-mode window tests."""

from __future__ import annotations


class _FakeVar:
    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", 620))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 520))


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.protocol_calls: list[tuple[str, object]] = []
        self.bind_calls: list[tuple[str, object, object | None]] = []
        self.update_idletasks_calls = 0
        self.destroy_calls = 0

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def destroy(self) -> None:
        self.destroy_calls += 1
