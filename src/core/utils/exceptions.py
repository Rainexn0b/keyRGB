from __future__ import annotations


def is_device_disconnected(exc: Exception) -> bool:
    """Best-effort check for a disappeared device.

    We intentionally keep this broad and dependency-free (no usb imports), since
    disconnects can surface as OSError, usb.core.USBError, RuntimeError, etc.
    """

    errno = getattr(exc, "errno", None)
    if errno == 19:
        return True

    try:
        msg = str(exc)
    except Exception:
        return False

    return "No such device" in msg


def is_device_busy(exc: Exception) -> bool:
    """Best-effort check for transient 'busy' errors."""

    errno = getattr(exc, "errno", None)
    if errno == 16:
        return True

    try:
        msg = str(exc)
    except Exception:
        return False

    return "Device or resource busy" in msg


def is_permission_denied(exc: Exception) -> bool:
    """Best-effort check for permission/authorization failures.

    Used to detect when hardware writes fail due to missing udev/polkit rules.
    Keep this dependency-free and resilient: backends may raise PermissionError,
    OSError with errno, or wrap errors with a descriptive message.
    """

    if isinstance(exc, PermissionError):
        return True

    errno = getattr(exc, "errno", None)
    if errno in (1, 13):
        # EPERM=1, EACCES=13
        return True

    try:
        msg = str(exc).lower()
    except Exception:
        return False

    return "permission denied" in msg or "access denied" in msg or "not permitted" in msg
