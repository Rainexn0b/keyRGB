#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, cast

DialogFileTypes: TypeAlias = list[tuple[str, str]]


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _TextWidget(_ConfigurableWidget, Protocol):
    def delete(self, start: str, end: str) -> None: ...

    def insert(self, index: str, value: str) -> None: ...


class _RootWidget(Protocol):
    def clipboard_clear(self) -> None: ...

    def clipboard_append(self, value: str) -> None: ...

    def after(self, delay_ms: int, callback: Callable[[], None]) -> None: ...


class _SaveAsFilenameFn(Protocol):
    def __call__(
        self,
        *,
        title: str,
        defaultextension: str,
        initialfile: str,
        filetypes: DialogFileTypes,
    ) -> str: ...


class _SupportWindowOutputLike(Protocol):
    root: _RootWidget
    status_label: _ConfigurableWidget

    def _set_status(self, text: str, *, ok: bool = True) -> None: ...


def _support_window(window: object) -> _SupportWindowOutputLike:
    return cast(_SupportWindowOutputLike, window)


def _text_widget(widget: object) -> _TextWidget:
    return cast(_TextWidget, widget)


def set_status(window: object, text: str, *, ok: bool = True) -> None:
    support_window = _support_window(window)
    color = "#00aa00" if ok else "#bb0000"
    support_window.status_label.configure(text=text, foreground=color)
    support_window.root.after(2500, lambda: support_window.status_label.configure(text=""))


def set_text(widget: object, text: str) -> None:
    text_widget = _text_widget(widget)
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", text)
    text_widget.configure(state="disabled")


def copy_text(
    window: object,
    text: str,
    *,
    empty_message: str,
    ok_message: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    support_window = _support_window(window)
    if not text:
        support_window._set_status(empty_message, ok=False)
        return
    try:
        support_window.root.clipboard_clear()
        support_window.root.clipboard_append(text)
    except tk_runtime_errors:
        support_window._set_status("Clipboard copy failed", ok=False)
        return
    support_window._set_status(ok_message, ok=True)


def save_text_via_dialog(
    window: object,
    text: str,
    *,
    title: str,
    initialfile: str,
    empty_message: str,
    asksaveasfilename: _SaveAsFilenameFn,
) -> None:
    support_window = _support_window(window)
    if not text:
        support_window._set_status(empty_message, ok=False)
        return

    filetypes: DialogFileTypes = [
        ("JSON files", "*.json"),
        ("Text files", "*.txt"),
        ("All files", "*.*"),
    ]
    path = asksaveasfilename(
        title=title,
        defaultextension=".json",
        initialfile=initialfile,
        filetypes=filetypes,
    )
    if not path:
        return

    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        support_window._set_status("Failed to save file", ok=False)
        return

    support_window._set_status("Saved output", ok=True)
