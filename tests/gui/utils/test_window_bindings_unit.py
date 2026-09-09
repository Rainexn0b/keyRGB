"""Unit tests for the shared main-window shortcut helper (UX-08)."""

from __future__ import annotations

from pathlib import Path

from keyrgb.gui.utils import window_bindings
from keyrgb.gui.utils.window_bindings import install_window_bindings


class _FakeRoot:
    """Minimal duck-typed Tk root (no Tkinter import)."""

    def __init__(self) -> None:
        self.bindings: list[tuple[str, object, str | None]] = []

    def bind(self, sequence: str, callback: object, add: str | None = None) -> None:
        self.bindings.append((sequence, callback, add))


def _sequences(root: _FakeRoot) -> list[str]:
    return [sequence for sequence, _, _ in root.bindings]


def test_module_is_tk_free() -> None:
    source = Path(window_bindings.__file__).read_text(encoding="utf-8")
    assert "import tkinter" not in source
    assert "from tkinter" not in source


def test_default_sequences_order_and_add_plus() -> None:
    root = _FakeRoot()
    install_window_bindings(root, on_close=lambda: None)
    assert _sequences(root) == ["<Control-w>", "<Escape>"]
    assert all(add == "+" for _, _, add in root.bindings)


def test_full_sequences_order_and_add_plus() -> None:
    root = _FakeRoot()
    install_window_bindings(root, on_close=lambda: None, on_save=lambda: None)
    assert _sequences(root) == ["<Control-w>", "<Escape>", "<Control-s>"]
    assert all(add == "+" for _, _, add in root.bindings)


def test_control_w_invokes_close_once_and_returns_break() -> None:
    root = _FakeRoot()
    calls: list[str] = []
    install_window_bindings(root, on_close=lambda: calls.append("close"))
    callback = root.bindings[0][1]
    assert callable(callback)
    result = callback(object())  # type: ignore[operator]
    assert result == "break"
    assert calls == ["close"]


def test_escape_invokes_close_once_and_returns_break() -> None:
    root = _FakeRoot()
    calls: list[str] = []
    install_window_bindings(root, on_close=lambda: calls.append("close"))
    callback = root.bindings[1][1]
    assert callback is root.bindings[0][1]  # shared close route wrapper
    assert callback(object()) == "break"  # type: ignore[operator]
    assert calls == ["close"]


def test_control_s_invokes_save_once_and_returns_break() -> None:
    root = _FakeRoot()
    closes: list[str] = []
    saves: list[str] = []
    install_window_bindings(root, on_close=lambda: closes.append("close"), on_save=lambda: saves.append("save"))
    callback = root.bindings[2][1]
    assert callback(object()) == "break"  # type: ignore[operator]
    assert saves == ["save"]
    assert closes == []


def test_close_wrapper_does_not_invoke_save() -> None:
    root = _FakeRoot()
    closes: list[str] = []
    saves: list[str] = []
    install_window_bindings(root, on_close=lambda: closes.append("close"), on_save=lambda: saves.append("save"))
    assert root.bindings[0][1](object()) == "break"  # type: ignore[operator]
    assert closes == ["close"]
    assert saves == []


def test_save_omitted_when_none() -> None:
    root = _FakeRoot()
    install_window_bindings(root, on_close=lambda: None, on_save=None)
    assert _sequences(root) == ["<Control-w>", "<Escape>"]


def test_escape_omitted_when_disabled() -> None:
    root = _FakeRoot()
    install_window_bindings(root, on_close=lambda: None, close_on_escape=False)
    assert _sequences(root) == ["<Control-w>"]
    root_with_save = _FakeRoot()
    install_window_bindings(root_with_save, on_close=lambda: None, on_save=lambda: None, close_on_escape=False)
    assert _sequences(root_with_save) == ["<Control-w>", "<Control-s>"]


def test_close_and_save_callbacks_are_distinct() -> None:
    root = _FakeRoot()
    install_window_bindings(root, on_close=lambda: None, on_save=lambda: None)
    close_wrapper = root.bindings[0][1]
    save_wrapper = root.bindings[2][1]
    assert close_wrapper is not save_wrapper


def test_no_native_navigation_or_uppercase_bindings() -> None:
    for kwargs in (
        {"close_on_escape": True},
        {"close_on_escape": False},
    ):
        root = _FakeRoot()
        install_window_bindings(root, on_close=lambda: None, on_save=lambda: None, **kwargs)  # type: ignore[arg-type]
        sequences = _sequences(root)
        assert "<Control-W>" not in sequences
        assert "<Control-S>" not in sequences
        for sequence in sequences:
            assert "Tab" not in sequence
            assert "Return" not in sequence
            assert "KP_Enter" not in sequence
            assert "Up" not in sequence
            assert "Down" not in sequence
            assert "Left" not in sequence
            assert "Right" not in sequence
            assert "<<" not in sequence
        assert set(sequences) <= {"<Control-w>", "<Escape>", "<Control-s>"}
