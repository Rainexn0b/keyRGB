"""Unit coverage for support probe dialog helpers with injected Tk fakes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.gui.windows._support import (
    _support_window_probe_dialog_layout as layout,
    _support_window_probe_dialogs as dialogs,
)


class _Root:
    def __init__(self) -> None:
        self.sw = 1000
        self.sh = 800
        self.rx = 10
        self.ry = 20
        self.w = 600
        self.h = 400

    def update_idletasks(self) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return self.sw

    def winfo_screenheight(self) -> int:
        return self.sh

    def winfo_rootx(self) -> int:
        return self.rx

    def winfo_rooty(self) -> int:
        return self.ry

    def winfo_width(self) -> int:
        return self.w

    def winfo_height(self) -> int:
        return self.h


class _Widget:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[Any, ...]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.inserted: list[tuple[str, str]] = []
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
        self.inserted.append((index, value))

    def get(self, start: str, end: str) -> str:
        return self._text

    def focus_set(self) -> None:
        self.focus += 1

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
        # auto-confirm via stored command if present
        cmd = self.kwargs.get("_auto")
        if callable(cmd):
            cmd()

    def winfo_width(self) -> int:
        return self._width


class _Tk:
    def __init__(self) -> None:
        self.last_dialog: _Widget | None = None

    def Toplevel(self, parent: object) -> _Widget:
        d = _Widget(parent=parent)
        self.last_dialog = d
        return d


class _Ttk:
    def Frame(self, parent: object, *, padding: int | None = None) -> _Widget:
        return _Widget(parent=parent, padding=padding)

    def Button(self, parent: object, *, text: str, command: object) -> _Widget:
        b = _Widget(text=text, command=command)
        b.commands["command"] = command
        return b

    def Label(self, parent: object, *, text: str, justify: str, wraplength: int) -> _Widget:
        return _Widget(text=text, justify=justify, wraplength=wraplength)


class _Scrolled:
    def ScrolledText(self, parent: object, **kwargs: object) -> _Widget:
        return _Widget(parent=parent, **kwargs)


def test_layout_dimensions_wrap_and_geometry() -> None:
    window = SimpleNamespace(root=_Root())
    assert layout._probe_dialog_dimensions(window, width=2000, height=2000) == (920, 736)

    broken = SimpleNamespace(root=SimpleNamespace(winfo_screenwidth=lambda: (_ for _ in ()).throw(RuntimeError("x"))))
    assert layout._probe_dialog_dimensions(broken, width=100, height=200) == (100, 200)

    container = _Widget()
    container._width = 0
    assert layout._dialog_wraplength(container, padding=10, minimum=50) == 50
    container._width = 300
    assert layout._dialog_wraplength(container, padding=40, minimum=50) == 260

    label = _Widget()
    layout._sync_dialog_prompt_wrap(label, container, padding=40, minimum=50)
    assert label.configure_calls

    dialog = _Widget()
    layout._bind_dialog_prompt_wrap(dialog, label, container, padding=40, minimum=50)
    assert dialog.bind_calls or container.bind_calls
    assert dialog.after_calls

    assert layout._probe_dialog_geometry(window, width=400, height=300).startswith("400x300+")
    assert layout._probe_dialog_geometry(broken, width=100, height=80) == "100x80"


def test_create_and_dismiss_probe_dialog() -> None:
    window = SimpleNamespace(root=_Root())
    tk = _Tk()
    ttk = _Ttk()
    dialog, container, width, height = layout._create_probe_dialog(
        window,
        "Title",
        tk,
        ttk,
        500,
        400,
        minsize=(300, 200),
        stretch_row=1,
    )
    assert width <= 500 and height <= 400
    assert dialog.kwargs["title"] == "Title"
    assert isinstance(container, _Widget)

    layout._dismiss_probe_dialog(dialog)
    assert dialog.released is True
    assert dialog.destroyed is True


def test_build_dialog_button_row_grids_actions() -> None:
    container = _Widget()
    ttk = _Ttk()
    buttons = layout._build_dialog_button_row(
        container,
        ttk=ttk,
        row=2,
        pady=(8, 0),
        actions=[("A", lambda: None), ("B", lambda: None), ("C", lambda: None)],
        columns=2,
    )
    assert len(buttons) == 3
    assert buttons[0].grid_calls[0]["column"] == 0
    assert buttons[1].grid_calls[0]["column"] == 1
    assert buttons[2].grid_calls[0]["row"] == 1


def test_show_probe_message_dialog_ok_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    window = SimpleNamespace(root=_Root(), _bg_color="#000", _fg_color="#fff")
    tk = _Tk()
    ttk = _Ttk()
    scrolled = _Scrolled()

    # Auto-click OK after dialog is created by hooking wait_window via create
    original_create = layout._create_probe_dialog

    def create_and_arm(*args: object, **kwargs: object):
        dialog, container, w, h = original_create(*args, **kwargs)

        def wait() -> None:
            # find OK command from last button build by invoking protocol?
            # The OK button is created after; use protocol after wait is set.
            pass

        dialog.wait_window = wait  # type: ignore[method-assign]
        return dialog, container, w, h

    # Patch wait_window on dialog class instances after show builds buttons:
    created: dict[str, Any] = {}

    def create_capture(*args: object, **kwargs: object):
        dialog, container, w, h = original_create(*args, **kwargs)
        created["dialog"] = dialog

        def auto_ok() -> None:
            # invoke WM protocol is cancel; instead call OK via stored action after build
            ok = created.get("ok")
            if callable(ok):
                ok()

        dialog.wait_window = auto_ok  # type: ignore[method-assign]
        return dialog, container, w, h

    monkeypatch.setattr(layout, "_create_probe_dialog", create_capture)
    monkeypatch.setattr(dialogs, "_dialog_layout", layout)

    original_buttons = layout._build_dialog_button_row

    def buttons_capture(*args: object, **kwargs: object):
        buttons = original_buttons(*args, **kwargs)
        if buttons:
            created["ok"] = buttons[0].commands.get("command") or buttons[0].kwargs.get("command")
        return buttons

    monkeypatch.setattr(layout, "_build_dialog_button_row", buttons_capture)
    monkeypatch.setattr(dialogs, "_build_dialog_button_row", buttons_capture)

    assert (
        dialogs._show_probe_message_dialog(
            window,
            title="T",
            message="hello",
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolled,
        )
        is True
    )

    # Cancel path via WM_DELETE_WINDOW
    def create_cancel(*args: object, **kwargs: object):
        dialog, container, w, h = original_create(*args, **kwargs)

        def auto_cancel() -> None:
            proto = dialog.protocols.get("WM_DELETE_WINDOW")
            if callable(proto):
                proto()

        dialog.wait_window = auto_cancel  # type: ignore[method-assign]
        return dialog, container, w, h

    monkeypatch.setattr(layout, "_create_probe_dialog", create_cancel)
    assert (
        dialogs._show_probe_message_dialog(
            window,
            title="T",
            message="",
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolled,
        )
        is False
    )


def test_ask_probe_choice_and_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    window = SimpleNamespace(root=_Root(), _bg_color="#111", _fg_color="#eee")
    tk = _Tk()
    ttk = _Ttk()
    scrolled = _Scrolled()

    original_create = layout._create_probe_dialog
    original_buttons = layout._build_dialog_button_row
    state: dict[str, Any] = {}

    def create_arm(*args: object, **kwargs: object):
        dialog, container, w, h = original_create(*args, **kwargs)

        def run() -> None:
            action = state.get("action")
            if callable(action):
                action()

        dialog.wait_window = run  # type: ignore[method-assign]
        state["dialog"] = dialog
        return dialog, container, w, h

    def buttons_arm(*args: object, **kwargs: object):
        buttons = original_buttons(*args, **kwargs)
        # choose first action
        if buttons:
            state["action"] = buttons[0].kwargs.get("command")
        return buttons

    monkeypatch.setattr(layout, "_create_probe_dialog", create_arm)
    monkeypatch.setattr(layout, "_build_dialog_button_row", buttons_arm)
    monkeypatch.setattr(dialogs, "_dialog_layout", layout)
    monkeypatch.setattr(dialogs, "_build_dialog_button_row", buttons_arm)

    choice = dialogs._ask_probe_choice_dialog(
        window,
        title="Choose",
        prompt="Pick",
        tk=tk,
        ttk=ttk,
        choices=[("One", 1), ("Two", 2)],
    )
    assert choice == 1

    # notes OK
    def buttons_ok(*args: object, **kwargs: object):
        buttons = original_buttons(*args, **kwargs)
        # OK is first
        if buttons:
            state["action"] = buttons[0].kwargs.get("command")
        return buttons

    monkeypatch.setattr(layout, "_build_dialog_button_row", buttons_ok)
    monkeypatch.setattr(dialogs, "_build_dialog_button_row", buttons_ok)
    notes = dialogs._ask_probe_notes_dialog(
        window,
        title="Notes",
        prompt="Say",
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolled,
    )
    assert notes == "note text"

    # notes cancel via second button
    def buttons_cancel(*args: object, **kwargs: object):
        buttons = original_buttons(*args, **kwargs)
        if len(buttons) >= 2:
            state["action"] = buttons[1].kwargs.get("command")
        return buttons

    monkeypatch.setattr(layout, "_build_dialog_button_row", buttons_cancel)
    monkeypatch.setattr(dialogs, "_build_dialog_button_row", buttons_cancel)
    assert (
        dialogs._ask_probe_notes_dialog(
            window,
            title="Notes",
            prompt="Say",
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolled,
        )
        is None
    )
