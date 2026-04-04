from __future__ import annotations

import tkinter as tk
from typing import Any


def on_backdrop_transparency_changed(
    app: Any,
    value: str,
    *,
    value_coercion_errors: tuple[type[BaseException], ...],
    tk_call_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Any,
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


def apply_backdrop_transparency_redraw(app: Any, *, log_boundary_exception: Any) -> None:
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
    app: Any,
    *,
    profiles: Any,
    value_coercion_errors: tuple[type[BaseException], ...],
    tk_call_errors: tuple[type[BaseException], ...],
    backdrop_persistence_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Any,
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
    app: Any,
    *,
    profiles: Any,
    tk_call_errors: tuple[type[BaseException], ...],
    backdrop_persistence_errors: tuple[type[BaseException], ...],
    log_boundary_exception: Any,
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
