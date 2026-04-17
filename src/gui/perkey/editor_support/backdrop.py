from __future__ import annotations

import tkinter as tk
from typing import Callable, Protocol

BoundaryLogger = Callable[[str, str, Exception], None]


class _TkVarProtocol(Protocol):
    def get(self) -> object: ...

    def set(self, value: object) -> None: ...


class _TkRootProtocol(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], None]) -> object: ...

    def after_cancel(self, identifier: object) -> object: ...


class _BackdropCanvasProtocol(Protocol):
    def redraw(self) -> None: ...

    def reload_backdrop_image(self) -> None: ...


class _BackdropProfilesProtocol(Protocol):
    def normalize_backdrop_mode(self, mode: object) -> str: ...

    def save_backdrop_transparency(self, transparency: object, name: str | None = None) -> None: ...

    def save_backdrop_mode(self, mode: object, name: str | None = None) -> None: ...


class _BackdropEditorProtocol(Protocol):
    root: _TkRootProtocol
    canvas: _BackdropCanvasProtocol
    backdrop_transparency: _TkVarProtocol
    _backdrop_mode_var: _TkVarProtocol
    _backdrop_transparency_redraw_job: object | None
    _backdrop_transparency_save_job: object | None
    profile_name: str | None

    def _apply_backdrop_transparency_redraw(self) -> None: ...

    def _persist_backdrop_transparency(self) -> None: ...


def on_backdrop_transparency_changed(
    app: _BackdropEditorProtocol,
    value: str,
    *,
    value_coercion_errors: tuple[type[BaseException], ...],
    tk_call_errors: tuple[type[BaseException], ...],
    log_boundary_exception: BoundaryLogger,
) -> None:
    try:
        transparency = int(round(float(value)))
    except value_coercion_errors:
        transparency = 0
    transparency = max(0, min(100, transparency))

    try:
        app.backdrop_transparency.set(float(transparency))
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_transparency_var",
            "Failed to update perkey backdrop transparency variable",
            exc,
        )

    if app._backdrop_transparency_redraw_job is not None:
        try:
            app.root.after_cancel(app._backdrop_transparency_redraw_job)
        except tk_call_errors as exc:
            log_boundary_exception(
                "perkey.editor.backdrop_transparency_redraw_cancel",
                "Failed to cancel pending perkey backdrop redraw",
                exc,
            )
    app._backdrop_transparency_redraw_job = app.root.after(30, app._apply_backdrop_transparency_redraw)

    if app._backdrop_transparency_save_job is not None:
        try:
            app.root.after_cancel(app._backdrop_transparency_save_job)
        except tk_call_errors as exc:
            log_boundary_exception(
                "perkey.editor.backdrop_transparency_save_cancel",
                "Failed to cancel pending perkey backdrop transparency save",
                exc,
            )
    app._backdrop_transparency_save_job = app.root.after(250, app._persist_backdrop_transparency)


def apply_backdrop_transparency_redraw(
    app: _BackdropEditorProtocol,
    *,
    log_boundary_exception: BoundaryLogger,
) -> None:
    app._backdrop_transparency_redraw_job = None
    try:
        app.canvas.redraw()
    except (RuntimeError, tk.TclError) as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_transparency_redraw",
            "Failed to redraw perkey backdrop transparency change",
            exc,
        )


def persist_backdrop_transparency(
    app: _BackdropEditorProtocol,
    *,
    profiles: _BackdropProfilesProtocol,
    value_coercion_errors: tuple[type[BaseException], ...],
    tk_call_errors: tuple[type[BaseException], ...],
    backdrop_persistence_errors: tuple[type[BaseException], ...],
    log_boundary_exception: BoundaryLogger,
) -> None:
    app._backdrop_transparency_save_job = None
    try:
        transparency = int(round(float(app.backdrop_transparency.get())))
    except value_coercion_errors + tk_call_errors:
        return

    try:
        profiles.save_backdrop_transparency(transparency, app.profile_name)
    except backdrop_persistence_errors as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_transparency_save",
            "Failed to persist perkey backdrop transparency",
            exc,
        )


def on_backdrop_mode_changed(
    app: _BackdropEditorProtocol,
    *,
    profiles: _BackdropProfilesProtocol,
    tk_call_errors: tuple[type[BaseException], ...],
    backdrop_persistence_errors: tuple[type[BaseException], ...],
    log_boundary_exception: BoundaryLogger,
) -> None:
    mode = profiles.normalize_backdrop_mode(app._backdrop_mode_var.get())
    try:
        app._backdrop_mode_var.set(mode)
    except tk_call_errors as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_mode_var",
            "Failed to update perkey backdrop mode variable",
            exc,
        )

    try:
        profiles.save_backdrop_mode(mode, app.profile_name)
    except backdrop_persistence_errors as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_mode_save",
            "Failed to persist perkey backdrop mode",
            exc,
        )
        return

    try:
        app.canvas.reload_backdrop_image()
    except (RuntimeError, tk.TclError) as exc:
        log_boundary_exception(
            "perkey.editor.backdrop_mode_reload",
            "Failed to reload perkey backdrop after mode change",
            exc,
        )
