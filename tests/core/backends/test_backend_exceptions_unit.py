"""Unit tests for the BackendError exception hierarchy."""

from __future__ import annotations

import pytest

from src.core.backends.exceptions import (
    BackendBusyError,
    BackendDisconnectedError,
    BackendError,
    BackendIOError,
    BackendPermissionError,
    BackendUnavailableError,
    format_backend_error,
)


# --- Hierarchy tests ---


def test_backend_permission_error_is_backend_error():
    exc = BackendPermissionError("denied")
    assert isinstance(exc, BackendError)


def test_backend_permission_error_is_permission_error():
    exc = BackendPermissionError("denied")
    assert isinstance(exc, PermissionError)


def test_backend_busy_error_is_oserror():
    exc = BackendBusyError("busy")
    assert isinstance(exc, OSError)


def test_backend_disconnected_error_is_oserror():
    exc = BackendDisconnectedError("gone")
    assert isinstance(exc, OSError)


def test_backend_io_error_is_oserror():
    exc = BackendIOError("io fail")
    assert isinstance(exc, OSError)


def test_all_subclasses_are_backend_error():
    for cls in (
        BackendUnavailableError,
        BackendPermissionError,
        BackendDisconnectedError,
        BackendBusyError,
        BackendIOError,
    ):
        assert issubclass(cls, BackendError)


# --- format_backend_error tests ---


def test_format_permission_error():
    msg = format_backend_error(BackendPermissionError("denied"))
    assert "udev" in msg.lower() or "permission" in msg.lower()


def test_format_busy_error():
    msg = format_backend_error(BackendBusyError("busy"))
    assert "busy" in msg.lower()


def test_format_disconnected_error():
    msg = format_backend_error(BackendDisconnectedError("gone"))
    assert "disconnect" in msg.lower()


def test_format_unavailable_error():
    msg = format_backend_error(BackendUnavailableError("not found"))
    assert "not found" in msg.lower() or "unavailable" in msg.lower()


def test_format_io_error():
    msg = format_backend_error(BackendIOError("ioctl failed"))
    assert "ioctl failed" in msg


def test_format_generic_backend_error():
    msg = format_backend_error(BackendError("unknown"))
    assert "unknown" in msg


def test_format_non_backend_error_fallback():
    msg = format_backend_error(ValueError("boom"))
    assert "boom" in msg


# --- Catch compatibility ---


def test_backend_permission_error_caught_as_permission_error():
    with pytest.raises(PermissionError):
        raise BackendPermissionError("denied")


def test_backend_io_error_caught_as_oserror():
    with pytest.raises(OSError):
        raise BackendIOError("io fail")
