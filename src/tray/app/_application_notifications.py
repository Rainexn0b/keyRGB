"""Best-effort tray notification and event-log helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable, MutableMapping
from typing import Protocol, TypeVar


_NOTIFICATION_BACKEND_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_NOTIFICATION_TWO_ARG_ERRORS = (AttributeError, OSError, RuntimeError)
_EVENT_LOGGING_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_ResultT = TypeVar("_ResultT")


class _EventThrottleTray(Protocol):
    @property
    def _event_last_at(self) -> MutableMapping[str, float]: ...


class _QueuedNotificationTray(Protocol):
    @property
    def icon(self) -> object | None: ...

    @property
    def _pending_notifications(self) -> list[tuple[str, str]]: ...


class _PermissionIssueTray(Protocol):
    _permission_notice_sent: bool
    backend: object | None

    def _notify(self, title: str, message: str) -> None: ...


class _SafeStrAttr(Protocol):
    def __call__(self, obj: object, name: str, *, default: str = "") -> str: ...


def _run_best_effort(
    operation: Callable[[], _ResultT],
    *,
    fallback: _ResultT,
    errors: tuple[type[BaseException], ...],
    on_error: Callable[[BaseException], None] | None = None,
) -> _ResultT:
    """Run a recoverable tray helper boundary with an optional fallback."""

    try:
        return operation()
    except errors as exc:  # @quality-exception exception-transparency: shared tray notification/backend and diagnostic logging boundaries must degrade on recoverable runtime failures while unexpected defects still propagate
        if on_error is not None:
            on_error(exc)
        return fallback


def _update_event_throttle(tray: _EventThrottleTray, msg: str, *, monotonic_fn: Callable[[], float]) -> bool:
    now = monotonic_fn()
    last = float(tray._event_last_at.get(msg, 0.0) or 0.0)
    if now - last < 1.0:
        return True
    tray._event_last_at[msg] = now
    return False


def notify(
    tray: _QueuedNotificationTray,
    title: str,
    message: str,
    *,
    logger: logging.Logger,
    shutil_module: object,
    subprocess_module: object,
) -> None:
    """Best-effort user notification with early queueing and notify-send fallback."""

    icon = getattr(tray, "icon", None)
    if icon is None:
        tray._pending_notifications.append((str(title), str(message)))
        return

    notify_fn = getattr(icon, "notify", None)
    if callable(notify_fn):

        def _notify_two_args() -> bool:
            notify_fn(str(message), str(title))
            return True

        def _notify_one_arg() -> bool:
            notify_fn(str(message))
            return True

        try:
            if _run_best_effort(
                _notify_two_args,
                fallback=False,
                errors=_NOTIFICATION_TWO_ARG_ERRORS,
                on_error=lambda exc: logger.debug("Pystray notification backend failed, trying notify-send: %s", exc),
            ):
                return
        except TypeError:
            if _run_best_effort(
                _notify_one_arg,
                fallback=False,
                errors=_NOTIFICATION_BACKEND_ERRORS,
            ):
                return

    which = getattr(shutil_module, "which", None)
    run = getattr(subprocess_module, "run", None)
    devnull = getattr(subprocess_module, "DEVNULL", None)

    try:
        if callable(which) and which("notify-send") and callable(run):
            run(
                ["notify-send", str(title), str(message)],
                check=False,
                stdout=devnull,
                stderr=devnull,
            )
    except OSError:
        return


def notify_permission_issue(
    tray: _PermissionIssueTray,
    exc: Exception | None = None,
    *,
    logger: logging.Logger,
    is_permission_denied: Callable[[BaseException], bool],
    build_permission_denied_message: Callable[[str], str],
    backend_error_cls: type[BaseException],
    format_backend_error: Callable[[BaseException], str],
    safe_str_attr: _SafeStrAttr,
) -> None:
    """Show a one-time permission notification for runtime lighting failures."""

    if tray._permission_notice_sent:
        return
    if exc is not None and not is_permission_denied(exc):
        return

    tray._permission_notice_sent = True

    backend = tray.backend
    backend_name = safe_str_attr(backend, "name", default="") if backend is not None else ""

    if exc is not None:
        logger.warning("Permission issue while applying lighting: %s", exc)

    title = (
        "KeyRGB: " + format_backend_error(exc)
        if exc is not None and isinstance(exc, backend_error_cls)
        else "KeyRGB: Permission denied"
    )
    tray._notify(title, build_permission_denied_message(backend_name))


def log_exception(msg: str, exc: Exception, *, logger: logging.Logger) -> None:
    logger.exception(msg, exc)


def log_event(
    tray: _EventThrottleTray,
    source: object,
    action: object,
    *,
    logger: logging.Logger,
    monotonic_fn: Callable[[], float],
    **fields: object,
) -> None:
    """Log a human-readable event cause without disrupting tray runtime."""

    event_parts = _run_best_effort(
        lambda: (str(source), str(action)),
        fallback=None,
        errors=_EVENT_LOGGING_ERRORS,
    )
    if event_parts is None:
        return
    src, act = event_parts

    parts: list[str] = []
    for key in sorted(fields.keys()):
        value = fields.get(key)

        def format_field() -> str:
            return f"{key}={value}"

        parts.append(
            _run_best_effort(
                format_field,
                fallback=f"{key}=<unrepr>",
                errors=_EVENT_LOGGING_ERRORS,
            )
        )

    msg = f"EVENT {src}:{act}"
    if parts:
        msg = f"{msg} " + " ".join(parts)

    if _run_best_effort(
        lambda: _update_event_throttle(tray, msg, monotonic_fn=monotonic_fn),
        fallback=False,
        errors=_EVENT_LOGGING_ERRORS,
    ):
        return

    _run_best_effort(
        lambda: logger.info("%s", msg),
        fallback=None,
        errors=_EVENT_LOGGING_ERRORS,
    )
