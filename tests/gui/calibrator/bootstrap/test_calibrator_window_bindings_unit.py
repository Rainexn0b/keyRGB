"""UX-08 calibrator accelerator bindings via the shared helper."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from keyrgb.gui.calibrator import _app_bootstrap as boot


class _Widget:
    def __init__(self, kind: str = "w", **kwargs: object) -> None:
        self.kind = kind
        self.kwargs = kwargs
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[object, ...]] = []

    def grid(self, *args: object, **kwargs: object) -> None:
        self.grid_calls.append(kwargs)

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def configure(self, **kwargs: object) -> None:
        pass

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        pass

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        pass

    def winfo_width(self) -> int:
        return 300

    def focus_set(self) -> None:
        pass


class _Tk:
    def Canvas(self, parent: object = None, **kwargs: object) -> _Widget:
        return _Widget("canvas", parent=parent, **kwargs)

    def BooleanVar(self, master: object = None, value: object = None, name: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(value=value, get=lambda: value)


class _Ttk:
    def Frame(self, parent: object = None, **kwargs: object) -> _Widget:
        return _Widget("frame", parent=parent, **kwargs)

    def Label(self, parent: object = None, **kwargs: object) -> _Widget:
        return _Widget("label", parent=parent, **kwargs)

    def Button(self, parent: object = None, **kwargs: object) -> _Widget:
        return _Widget("button", parent=parent, **kwargs)

    def Checkbutton(self, parent: object = None, **kwargs: object) -> _Widget:
        return _Widget("check", parent=parent, **kwargs)


class _App:
    def __init__(self) -> None:
        self.bg_color = "#101010"
        self.bind_calls: list[tuple[Any, ...]] = []
        self.after_calls: list[tuple[int, object]] = []
        self._focused: object = None
        self._redraw = MagicMock()
        self._on_click = MagicMock()
        self._prev = MagicMock()
        self._next = MagicMock()
        self._assign = MagicMock()
        self._skip = MagicMock()
        self._on_show_backdrop_changed = MagicMock()
        self._reset_keymap_defaults = MagicMock()
        self._save = MagicMock()
        self._save_and_close = MagicMock()
        self._on_close = MagicMock()

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        pass

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        pass

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def after(self, delay_ms: int, callback: object) -> None:
        self.after_calls.append((delay_ms, callback))

    def focus_get(self) -> object:
        return self._focused


def _build() -> _App:
    app = _App()
    boot.build_widgets(app, tk=_Tk(), ttk=_Ttk(), tk_runtime_errors=(RuntimeError,), wrap_sync_errors=(RuntimeError,))
    return app


def _callbacks_for(app: _App, sequence: str) -> list[object]:
    return [cb for seq, cb, _add in app.bind_calls if seq == sequence]


def test_shared_shortcuts_installed_once_with_break() -> None:
    app = _build()
    sequences = [seq for seq, _cb, _add in app.bind_calls]
    assert sequences.count("<Escape>") == 1
    assert "<Control-w>" in sequences
    assert "<Control-s>" in sequences
    for seq in ("<Control-w>", "<Escape>", "<Control-s>"):
        cbs = _callbacks_for(app, seq)
        assert len(cbs) == 1
        assert cbs[0](object()) == "break"  # type: ignore[operator]
        add = next(add for s, _cb, add in app.bind_calls if s == seq)
        assert add == "+"


def test_close_shortcuts_route_to_on_close() -> None:
    app = _build()
    for seq in ("<Control-w>", "<Escape>"):
        cb = _callbacks_for(app, seq)[0]
        cb(object())  # type: ignore[operator]
    assert app._on_close.call_count == 2
    app._save.assert_not_called()
    app._save_and_close.assert_not_called()


def test_save_shortcut_uses_save_not_save_and_close() -> None:
    app = _build()
    cb = _callbacks_for(app, "<Control-s>")[0]
    assert cb(object()) == "break"  # type: ignore[operator]
    app._save.assert_called_once()
    app._save_and_close.assert_not_called()
    app._on_close.assert_not_called()


def test_probe_navigation_and_assignment_preserved() -> None:
    app = _build()
    by_seq = {seq: cb for seq, cb, _add in app.bind_calls}
    by_seq["<Return>"](object())  # type: ignore[operator]
    by_seq["<KP_Enter>"](object())  # type: ignore[operator]
    assert app._assign.call_count == 2
    by_seq["<Right>"](object())  # type: ignore[operator]
    app._next.assert_called_once()
    by_seq["<Left>"](object())  # type: ignore[operator]
    app._prev.assert_called_once()
