"""Widget protocols for support probe dialogs.

Owns the structural ``Protocol``/``TypeAlias`` surface shared by the probe
dialog builders and the dialog-layout module so
``_support_window_probe_dialogs.py`` stays small. Adds no behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, TypeVar

_GridPadding: TypeAlias = tuple[int, int]
_DialogAction: TypeAlias = Callable[[], None]
_DialogBindCallback: TypeAlias = Callable[[object | None], object]
_ChoiceValueT = TypeVar("_ChoiceValueT")  # noqa: PYI018 - re-exported via _support_window_probe_dialogs


class _ProbeDialogRoot(Protocol):
    def update_idletasks(self) -> None: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...

    def winfo_rootx(self) -> int: ...

    def winfo_rooty(self) -> int: ...

    def winfo_width(self) -> int: ...

    def winfo_height(self) -> int: ...


class _ProbeDialogWindow(Protocol):
    root: _ProbeDialogRoot


class _ThemedProbeDialogWindow(_ProbeDialogWindow, Protocol):  # noqa: PYI046 - re-exported via dialogs
    _bg_color: str
    _fg_color: str


class _WidthWidget(Protocol):
    def winfo_width(self) -> int: ...


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _FocusableWidget(Protocol):
    def focus_set(self) -> None: ...


class _GridWidget(Protocol):
    def grid(
        self,
        *,
        row: int,
        column: int,
        sticky: str,
        padx: _GridPadding | None = None,
        pady: _GridPadding | None = None,
    ) -> None: ...


class _BindableWidget(Protocol):
    def bind(self, sequence: str, callback: _DialogBindCallback, add: str | None = None) -> None: ...


class _DialogContainer(_WidthWidget, _BindableWidget, _GridWidget, Protocol):
    def pack(self, *, fill: str, expand: bool = False) -> None: ...

    def columnconfigure(self, index: int, weight: int = 0) -> None: ...

    def rowconfigure(self, index: int, weight: int = 0) -> None: ...


class _DialogButton(_GridWidget, _FocusableWidget, Protocol):
    pass


class _DialogLabel(_GridWidget, _ConfigurableWidget, Protocol):
    pass


class _DialogTextWidget(_GridWidget, _FocusableWidget, _ConfigurableWidget, Protocol):
    def insert(self, index: str, value: str) -> None: ...

    def get(self, start: str, end: str) -> str: ...


class _DialogWidget(_BindableWidget, Protocol):
    def title(self, value: str) -> None: ...

    def transient(self, parent: object) -> None: ...

    def geometry(self, value: str) -> None: ...

    def minsize(self, width: int, height: int) -> None: ...

    def resizable(self, width: bool, height: bool) -> None: ...

    def protocol(self, name: str, callback: _DialogAction) -> None: ...

    def after(self, delay_ms: int, callback: _DialogAction) -> None: ...

    def grab_set(self) -> None: ...

    def grab_release(self) -> None: ...

    def destroy(self) -> None: ...

    def wait_window(self) -> None: ...

    def focus_get(self) -> object: ...


class _FrameFactory(Protocol):
    def __call__(self, parent: object, *, padding: int | None = None) -> _DialogContainer: ...


class _ButtonFactory(Protocol):
    def __call__(self, parent: object, *, text: str, command: _DialogAction) -> _DialogButton: ...


class _LabelFactory(Protocol):
    def __call__(self, parent: object, *, text: str, justify: str, wraplength: int) -> _DialogLabel: ...


class _ScrolledTextFactory(Protocol):
    def __call__(
        self,
        parent: object,
        *,
        wrap: str,
        height: int,
        background: str,
        foreground: str,
        insertbackground: str,
    ) -> _DialogTextWidget: ...


class _ToplevelFactory(Protocol):
    def __call__(self, parent: object) -> _DialogWidget: ...


class _TtkDialogModule(Protocol):  # noqa: PYI046 - re-exported via dialogs
    Frame: _FrameFactory
    Button: _ButtonFactory
    Label: _LabelFactory


class _TkDialogModule(Protocol):  # noqa: PYI046 - re-exported via dialogs
    Toplevel: _ToplevelFactory


class _ScrolledTextModule(Protocol):  # noqa: PYI046 - re-exported via dialogs
    ScrolledText: _ScrolledTextFactory
