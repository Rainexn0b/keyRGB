from __future__ import annotations


def _safe_exception_message(exc: BaseException, *, lower: bool = False) -> str | None:
    try:
        msg = str(exc)
    except Exception:  # @quality-exception exception-transparency: arbitrary exception __str__ implementations may fail and these dependency-free boolean helpers must stay non-fatal and noiseless
        return None

    return msg.lower() if lower else msg


def is_device_disconnected(exc: BaseException) -> bool:
    """Best-effort check for a disappeared device.

    We intentionally keep this broad and dependency-free (no usb imports), since
    disconnects can surface as OSError, usb.core.USBError, RuntimeError, etc.
    """

    errno = getattr(exc, "errno", None)
    if errno == 19:
        return True

    msg = _safe_exception_message(exc)
    if msg is None:
        return False

    return "No such device" in msg


def is_device_busy(exc: BaseException) -> bool:
    """Best-effort check for transient 'busy' errors."""

    errno = getattr(exc, "errno", None)
    if errno == 16:
        return True

    msg = _safe_exception_message(exc)
    if msg is None:
        return False

    return "Device or resource busy" in msg


def is_permission_denied(exc: BaseException) -> bool:
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

    msg = _safe_exception_message(exc, lower=True)
    if msg is None:
        return False

    return "permission denied" in msg or "access denied" in msg or "not permitted" in msg
