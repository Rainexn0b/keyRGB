"""Focused UX-08 key-binding coverage for support probe dialogs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

from keyrgb.gui.windows._support import (
    _support_window_probe_dialog_layout as layout,
    _support_window_probe_dialogs as dialogs,
)


class _Widget:
    focused_widget: ClassVar[_Widget | None] = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[Any, ...]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.destroyed = False
        self.grabbed = False
        self.released = False
        self.protocols: dict[str, object] = {}
        self.after_calls: list[tuple[int, object]] = []
        self.focus = 0
        self._text = "note text\n"
        self._width = 400
        self.commands: dict[str, object] = {}

    def pack(self, **kwargs: object) -> None:
        pass

    def grid(self, **kwargs: object) -> None:
        self.grid_calls.append(kwargs)

    def columnconfigure(self, index: int, weight: int = 0) -> None:
        pass

    def rowconfigure(self, index: int, weight: int = 0) -> None:
        pass

    def bind(self, sequence: str, callback: object, add: str | None = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)

    def insert(self, index: str, value: str) -> None:
        pass

    def get(self, start: str, end: str) -> str:
        return self._text

    def focus_set(self) -> None:
        self.focus += 1
        type(self).focused_widget = self

    def focus_get(self) -> object | None:
        return type(self).focused_widget

    def title(self, value: str) -> None:
        self.kwargs["title"] = value

    def transient(self, parent: object) -> None:
        self.kwargs["transient"] = parent

    def geometry(self, value: str) -> None:
        self.kwargs["geometry"] = value

    def minsize(self, width: int, height: int) -> None:
        self.kwargs["minsize"] = (width, height)

    def resizable(self, width: bool, height: bool) -> None:
        self.kwargs["resizable"] = (width, height)

    def protocol(self, name: str, callback: object) -> None:
        self.protocols[name] = callback

    def after(self, delay_ms: int, callback: object) -> None:
        self.after_calls.append((delay_ms, callback))

    def grab_set(self) -> None:
        self.grabbed = True

    def grab_release(self) -> None:
        self.released = True

    def destroy(self) -> None:
        self.destroyed = True

    def wait_window(self) -> None:
        cmd = self.kwargs.get("_auto")
        if callable(cmd):
            cmd()

    def winfo_width(self) -> int:
        return self._width


class _Root:
    def update_idletasks(self) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return 1000

    def winfo_screenheight(self) -> int:
        return 800

    def winfo_rootx(self) -> int:
        return 10

    def winfo_rooty(self) -> int:
        return 20

    def winfo_width(self) -> int:
        return 600

    def winfo_height(self) -> int:
        return 400


class _Tk:
    def __init__(self) -> None:
        self.last_dialog: _Widget | None = None

    def Toplevel(self, parent: object) -> _Widget:
        d = _Widget(parent=parent)
        self.last_dialog = d
        return d


class _Ttk:
    def __init__(self) -> None:
        self.buttons: list[_Widget] = []

    def Frame(self, parent: object, *, padding: int | None = None) -> _Widget:
        return _Widget(parent=parent, padding=padding)

    def Button(self, parent: object, *, text: str, command: object) -> _Widget:
        b = _Widget(text=text, command=command)
        b.commands["command"] = command
        self.buttons.append(b)
        return b

    def Label(self, parent: object, *, text: str, justify: str, wraplength: int) -> _Widget:
        return _Widget(text=text, justify=justify, wraplength=wraplength)


class _Scrolled:
    def ScrolledText(self, parent: object, **kwargs: object) -> _Widget:
        return _Widget(parent=parent, **kwargs)


def _sequences(dialog: _Widget) -> list[str]:
    return [seq for seq, _, _ in dialog.bind_calls]


def _handler(dialog: _Widget, sequence: str) -> Any:
    for seq, cb, _add in dialog.bind_calls:
        if seq == sequence:
            return cb
    raise AssertionError(f"missing binding {sequence}")


def _run_with_key(monkeypatch, dialog_fn, key_sequence: str | None, **kwargs):
    """Run a probe dialog, firing one dialog-level key binding inside wait."""
    window = SimpleNamespace(root=_Root(), _bg_color="#000", _fg_color="#fff")
    tk = _Tk()
    ttk = _Ttk()
    scrolled = _Scrolled()
    original_create = layout._create_probe_dialog
    state: dict[str, Any] = {}

    def create_and_fire(*args: object, **call_kwargs: object):
        dialog, container, w, h = original_create(*args, **call_kwargs)
        state["dialog"] = dialog

        def _wait() -> None:
            if key_sequence is None:
                return
            handler = _handler(dialog, key_sequence)
            handler(None)

        dialog.wait_window = _wait  # type: ignore[method-assign]
        return dialog, container, w, h

    monkeypatch.setattr(layout, "_create_probe_dialog", create_and_fire)
    monkeypatch.setattr(dialogs, "_dialog_layout", layout)
    result = dialog_fn(window, tk=tk, ttk=ttk, scrolledtext=scrolled, **kwargs)
    return result, state["dialog"]


def test_message_dialog_escape_follows_wm_cancel(monkeypatch) -> None:
    result, dialog = _run_with_key(
        monkeypatch,
        dialogs._show_probe_message_dialog,
        "<Escape>",
        title="T",
        message="hi",
    )
    assert result is False
    assert dialog.released is True
    assert dialog.destroyed is True
    assert _sequences(dialog) == ["<Escape>", "<Return>", "<KP_Enter>"]
    assert all(add == "+" for _, _, add in dialog.bind_calls)
    # WM_DELETE_WINDOW stays wired to the same cancel route.
    assert callable(dialog.protocols.get("WM_DELETE_WINDOW"))
    # Native transient/geometry preserved.
    assert "transient" in dialog.kwargs
    assert "geometry" in dialog.kwargs


def test_message_dialog_return_and_kp_enter_confirm(monkeypatch) -> None:
    for sequence in ("<Return>", "<KP_Enter>"):
        result, dialog = _run_with_key(
            monkeypatch,
            dialogs._show_probe_message_dialog,
            sequence,
            title="T",
            message="hi",
        )
        assert result is True
        assert dialog.released is True
        assert dialog.destroyed is True


def test_choice_dialog_escape_cancels_and_returns_confirm_first_choice(monkeypatch) -> None:
    window = SimpleNamespace(root=_Root())
    tk = _Tk()
    ttk = _Ttk()
    original_create = layout._create_probe_dialog
    state: dict[str, Any] = {}

    def create_and_capture(*args: object, **kwargs: object):
        dialog, container, w, h = original_create(*args, **kwargs)
        state["dialog"] = dialog

        def _wait() -> None:
            focus_index = state.get("focus_index")
            if isinstance(focus_index, int):
                ttk.buttons[focus_index].focus_set()
            handler = _handler(dialog, state["fire"])
            handler(None)

        dialog.wait_window = _wait  # type: ignore[method-assign]
        return dialog, container, w, h

    monkeypatch.setattr(layout, "_create_probe_dialog", create_and_capture)
    monkeypatch.setattr(dialogs, "_dialog_layout", layout)

    for sequence, expected, focus_index in (
        ("<Escape>", None, None),
        ("<Return>", 1, None),
        ("<KP_Enter>", 1, None),
        ("<Return>", 2, 1),
    ):
        ttk.buttons.clear()
        state["fire"] = sequence
        state["focus_index"] = focus_index
        result = dialogs._ask_probe_choice_dialog(
            window,
            title="Choose",
            prompt="Pick",
            tk=tk,
            ttk=ttk,
            choices=[("One", 1), ("Two", 2)],
        )
        assert result == expected
        dialog = state["dialog"]
        assert dialog.released is True
        assert dialog.destroyed is True
        key_sequences = [seq for seq in _sequences(dialog) if seq in ("<Escape>", "<Return>", "<KP_Enter>")]
        assert key_sequences == ["<Escape>", "<Return>", "<KP_Enter>"]
        assert "<Configure>" in _sequences(dialog)
        assert all(add == "+" for seq, _, add in dialog.bind_calls if seq in ("<Escape>", "<Return>", "<KP_Enter>"))


def test_notes_dialog_escape_cancels_and_has_no_return_binding(monkeypatch) -> None:
    result, dialog = _run_with_key(
        monkeypatch,
        dialogs._ask_probe_notes_dialog,
        "<Escape>",
        title="Notes",
        prompt="Say",
    )
    assert result is None
    assert dialog.released is True
    assert dialog.destroyed is True
    key_sequences = [seq for seq in _sequences(dialog) if seq in ("<Escape>", "<Return>", "<KP_Enter>")]
    assert key_sequences == ["<Escape>"]
    assert "<Configure>" in _sequences(dialog)
    assert all(add == "+" for seq, _, add in dialog.bind_calls if seq == "<Escape>")
    assert "<Return>" not in _sequences(dialog)
    assert "<KP_Enter>" not in _sequences(dialog)
