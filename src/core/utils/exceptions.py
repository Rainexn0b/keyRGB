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
