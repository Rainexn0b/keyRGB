"""Backend exception hierarchy.

All exceptions raised by backend ``get_device()`` and transport layers are
translated into these types so that callers can use precise catch clauses
instead of ``except Exception``.

Inheritance is designed for backward compatibility:
- ``BackendPermissionError`` inherits from both ``BackendError`` and
  ``PermissionError`` so existing ``except PermissionError:`` sites still work.
- ``BackendBusyError`` inherits from ``OSError`` so ``is_device_busy()`` still
  works on the exception instance.
- ``BackendDisconnectedError`` inherits from ``OSError`` so
  ``is_device_disconnected()`` still works.
"""

from __future__ import annotations


class BackendError(Exception):
    """Base class for all backend hardware / driver errors."""


class BackendUnavailableError(BackendError):
    """Device was not detected at initialization time."""


class BackendPermissionError(BackendError, PermissionError):
    """Access denied — udev rules or polkit authorization missing."""


class BackendDisconnectedError(BackendError, OSError):
    """Device was present but has disconnected."""


class BackendBusyError(BackendError, OSError):
    """Device is held by another process."""


class BackendIOError(BackendError, OSError):
    """A hardware I/O operation failed on a detected device."""


def format_backend_error(exc: BaseException) -> str:
    """Return a short, user-facing description of a backend error.

    Suitable for status labels and tray notifications.  Falls back to a
    generic message when the exception is not a recognized BackendError
    subclass.
    """

    if isinstance(exc, BackendPermissionError):
        return "Permission denied — install udev rules and reload, or reboot"
    if isinstance(exc, BackendBusyError):
        return "Device busy — close other RGB apps and try again"
    if isinstance(exc, BackendDisconnectedError):
        return "Device disconnected"
    if isinstance(exc, BackendUnavailableError):
        return "Device not found"
    if isinstance(exc, BackendIOError):
        return f"Hardware I/O error: {exc}"
    if isinstance(exc, BackendError):
        return f"Backend error: {exc}"
    return f"Unexpected error: {exc}"
