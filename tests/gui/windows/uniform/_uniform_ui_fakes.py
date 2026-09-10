"""Shared fakes for uniform-color window UI tests."""

from __future__ import annotations


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []
        self.focus_calls = 0

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def focus_set(self) -> None:
        self.focus_calls += 1

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 560))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 640))


class _FakeRoot:
    def __init__(self, *, focused: object = None) -> None:
        self._focused = focused
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0
        self.protocol_calls: list[tuple[str, object]] = []
        self.bind_calls: list[tuple[str, object, object | None]] = []

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

    def focus_get(self) -> object:
        return self._focused

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600

    def destroy(self) -> None:
        self.destroy_calls += 1

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))


class _FakeColorWheel:
    def __init__(self, parent, *, size: int, initial_color: tuple[int, int, int], callback, release_callback) -> None:
        self.parent = parent
        self.size = size
        self.initial_color = initial_color
        self.callback = callback
        self.release_callback = release_callback
        self.pack_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def get_color(self) -> tuple[int, int, int]:
        return self.initial_color
