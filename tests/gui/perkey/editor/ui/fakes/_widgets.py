"""Tk stand-in widgets for per-key editor UI tests."""

from __future__ import annotations


class _FakeVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.configure_calls = []
        self.pack_calls = []
        self.grid_calls = []
        self.bind_calls = []
        self.columnconfigure_calls = []
        self.rowconfigure_calls = []
        self.grid_remove_calls = 0
        self.pack_propagate_calls = []
        self.focus_set_calls = 0
        self.width = int(kwargs.get("width", 360))
        self.reqwidth = int(kwargs.get("reqwidth", kwargs.get("width", 0)))
        self.children = []
        if hasattr(parent, "children"):
            parent.children.append(self)

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    config = configure

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, event, callback, add=None) -> None:
        self.bind_calls.append((event, callback, add))

    def columnconfigure(self, index, **kwargs) -> None:
        self.columnconfigure_calls.append({"index": index, **kwargs})

    def rowconfigure(self, index, **kwargs) -> None:
        self.rowconfigure_calls.append({"index": index, **kwargs})

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1

    def pack_propagate(self, flag) -> None:
        self.pack_propagate_calls.append(flag)

    def focus_set(self) -> None:
        self.focus_set_calls += 1

    def winfo_width(self) -> int:
        return int(self.width)

    def winfo_reqwidth(self) -> int:
        return int(self.reqwidth)

    def winfo_children(self):
        return list(self.children)


class _FakeRoot:
    def __init__(self, *, bind_error: bool = False):
        self.bind_error = bind_error
        self.bind_calls = []
        self.bound_callbacks = {}
        self.after_calls = []
        self.focused = None

    def bind(self, event, callback, add=None) -> None:
        if self.bind_error:
            raise RuntimeError("bind failed")
        self.bind_calls.append((event, callback, add))
        self.bound_callbacks[event] = callback

    def after(self, delay_ms, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def focus_get(self):
        return self.focused


class _FakeKeyboardCanvas:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeColorWheel:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []
        self.reqwidth = int(kwargs.get("reqwidth", kwargs.get("size", 0)))
        if hasattr(parent, "children"):
            parent.children.append(self)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def winfo_reqwidth(self) -> int:
        return int(self.reqwidth)
