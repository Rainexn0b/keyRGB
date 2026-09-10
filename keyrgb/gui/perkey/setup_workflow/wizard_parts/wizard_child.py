"""Guided calibrator child-process lifecycle for the setup wizard."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from .wizard_shared import (
    _CALIBRATOR_POLL_MS,
    _WIZARD_ERRORS,
    ChildProcessProtocol,
    GuidedResultAdopter,
    GuidedSessionFactory,
    SessionCleaner,
    WizardHost,
)

logger = logging.getLogger(__name__)


def resolve_child_launcher(explicit: Callable[[object], object] | None) -> Callable[[object], object]:
    if explicit is not None:
        return explicit
    from keyrgb.gui.calibrator.launch import launch_guided_calibrator

    return cast(Callable[[object], object], launch_guided_calibrator)


def start_child_process(
    host: WizardHost,
    *,
    create_session_fn: GuidedSessionFactory,
    cleanup_fn: SessionCleaner,
    launcher_fn: Callable[[object], object],
) -> None:
    allowed, message = host.controller.can_launch_calibrator()
    if not allowed:
        host._set_message(message)
        return
    try:
        session_path = create_session_fn(
            host.controller.draft,
            rows=host.controller.rows,
            cols=host.controller.cols,
        )
    except _WIZARD_ERRORS as exc:
        host._set_message(f"Could not prepare the guided session: {exc}")
        return
    try:
        process = launcher_fn(session_path)
    except _WIZARD_ERRORS as exc:
        cleanup_fn(session_path)
        host._set_message(f"Could not launch the guided calibrator: {exc}")
        return
    host._child_process = cast(ChildProcessProtocol, process)
    host.controller.note_child_started(session_path)
    host._set_message("Guided calibrator running; finish it (or close it) to continue.")
    host._refresh_nav()
    host._after(_CALIBRATOR_POLL_MS, host._poll_child)


def poll_child_process(host: WizardHost) -> None:
    process = host._child_process
    if process is None or not host.controller.child_running:
        return
    try:
        exited = process.poll() is not None
    except _WIZARD_ERRORS as exc:
        logger.debug("guided setup calibrator poll failed: %s", exc)
        host._after(_CALIBRATOR_POLL_MS, host._poll_child)
        return
    if not exited:
        host._after(_CALIBRATOR_POLL_MS, host._poll_child)
        return
    host._finish_child()


def finish_child_process(host: WizardHost, *, adopt_fn: GuidedResultAdopter) -> None:
    session_path = host.controller.session_path
    host._child_process = None
    adopted, message = adopt_fn(host.controller, session_path)
    host._set_message(message if not adopted else f"{message} You may continue.")
    cleanup_session_reference(host)
    host._render()


def cleanup_child_session(host: WizardHost, *, cleanup_fn: SessionCleaner) -> None:
    session_path = host.controller.session_path
    host._stop_polling()
    host._child_process = None
    if host.controller.child_running:
        # Never terminate the child; normal close is refused while it
        # runs, so reaching here means finish-after-exit or teardown.
        host.controller.note_child_finished()
    cleanup_fn(session_path)
    cleanup_session_reference(host)


def cleanup_session_reference(host: WizardHost) -> None:
    host.controller.session_path = None
