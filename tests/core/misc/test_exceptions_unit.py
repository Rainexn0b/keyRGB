"""Unit tests for low-level exception classification helpers."""

from __future__ import annotations

import pytest

from src.core.utils.exceptions import is_device_busy, is_device_disconnected, is_permission_denied


class _BrokenStrError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("broken __str__")


@pytest.mark.parametrize(
    ("helper", "exc"),
    [
        (is_device_disconnected, OSError(19, "ignored")),
        (is_device_busy, OSError(16, "ignored")),
        (is_permission_denied, OSError(13, "ignored")),
        (is_permission_denied, PermissionError("ignored")),
    ],
)
def test_helpers_match_errno_or_type_without_stringification(helper, exc: BaseException) -> None:
    assert helper(exc) is True


@pytest.mark.parametrize(
    ("helper", "exc"),
    [
        (is_device_disconnected, RuntimeError("No such device")),
        (is_device_busy, RuntimeError("Device or resource busy")),
        (is_permission_denied, RuntimeError("Access denied while opening device")),
        (is_permission_denied, RuntimeError("operation not permitted by policy")),
    ],
)
def test_helpers_match_expected_error_messages(helper, exc: BaseException) -> None:
    assert helper(exc) is True


@pytest.mark.parametrize(
    "helper",
    [is_device_disconnected, is_device_busy, is_permission_denied],
)
def test_helpers_return_false_when_exception_stringification_breaks(helper) -> None:
    assert helper(_BrokenStrError()) is False


@pytest.mark.parametrize(
    "helper",
    [is_device_disconnected, is_device_busy, is_permission_denied],
)
def test_helpers_propagate_unexpected_stringification_failures(helper) -> None:
    class _UnexpectedBrokenStrError(Exception):
        def __str__(self) -> str:
            raise AssertionError("unexpected __str__ bug")

    with pytest.raises(AssertionError, match="unexpected __str__ bug"):
        helper(_UnexpectedBrokenStrError())
