from __future__ import annotations

import logging
from types import TracebackType

import pytest
from unittest.mock import MagicMock, patch

from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


def _assert_logged_debug_traceback(
    logger: MagicMock,
    message: str,
    *,
    exc_type: type[BaseException] = RuntimeError,
    exc_message: str = "boom",
) -> None:
    logger.log.assert_called_once()
    assert logger.log.call_args.args == (logging.DEBUG, message)
    assert set(logger.log.call_args.kwargs) == {"exc_info"}
    exc_info = logger.log.call_args.kwargs["exc_info"]
    assert isinstance(exc_info, tuple)
    assert len(exc_info) == 3
    logged_type, logged_exc, logged_tb = exc_info
    assert logged_type is exc_type
    assert isinstance(logged_exc, exc_type)
    assert str(logged_exc) == exc_message
    assert isinstance(logged_tb, TracebackType)


def test_select_backend_with_introspection_happy_path() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.return_value = {"ok": True}
    backend.capabilities.return_value = {"per_key": False}

    with patch("src.tray.app.backend.select_backend", return_value=backend):
        b, probe, caps = select_backend_with_introspection()

    assert b is backend
    assert probe == {"ok": True}
    assert caps == {"per_key": False}


def test_load_ite_dimensions_falls_back_and_logs_traceback() -> None:
    from src.tray.app.backend import load_ite_dimensions

    logger = MagicMock()

    with (
        patch("src.tray.app.backend.logging.getLogger", return_value=logger),
        patch("src.tray.app.backend.select_backend", side_effect=RuntimeError("boom")),
    ):
        dims = load_ite_dimensions()

    assert dims == (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)
    _assert_logged_debug_traceback(logger, "Falling back to default keyboard dimensions")


def test_load_ite_dimensions_propagates_unexpected_errors() -> None:
    from src.tray.app.backend import load_ite_dimensions

    with patch("src.tray.app.backend.select_backend", side_effect=AssertionError("unexpected backend bug")):
        with pytest.raises(AssertionError, match="unexpected backend bug"):
            load_ite_dimensions()


def test_select_backend_with_introspection_handles_probe_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.side_effect = RuntimeError("boom")
    backend.capabilities.return_value = "caps"
    logger = MagicMock()

    with (
        patch("src.tray.app.backend.logging.getLogger", return_value=logger),
        patch("src.tray.app.backend.select_backend", return_value=backend),
    ):
        b, probe, caps = select_backend_with_introspection()

    assert b is backend
    assert probe is None
    assert caps == "caps"
    _assert_logged_debug_traceback(logger, "Backend probe failed during tray introspection")


def test_select_backend_with_introspection_propagates_unexpected_probe_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.side_effect = AssertionError("unexpected probe bug")
    backend.capabilities.return_value = "caps"

    with patch("src.tray.app.backend.select_backend", return_value=backend):
        with pytest.raises(AssertionError, match="unexpected probe bug"):
            select_backend_with_introspection()


def test_select_backend_with_introspection_handles_caps_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.return_value = "probe"
    backend.capabilities.side_effect = RuntimeError("boom")
    logger = MagicMock()

    with (
        patch("src.tray.app.backend.logging.getLogger", return_value=logger),
        patch("src.tray.app.backend.select_backend", return_value=backend),
    ):
        b, probe, caps = select_backend_with_introspection()

    assert b is backend
    assert probe == "probe"
    assert caps is None
    _assert_logged_debug_traceback(logger, "Backend capabilities lookup failed during tray introspection")


def test_select_backend_with_introspection_propagates_unexpected_caps_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.return_value = "probe"
    backend.capabilities.side_effect = AssertionError("unexpected caps bug")

    with patch("src.tray.app.backend.select_backend", return_value=backend):
        with pytest.raises(AssertionError, match="unexpected caps bug"):
            select_backend_with_introspection()


def test_select_backend_with_introspection_handles_none_backend() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    with patch("src.tray.app.backend.select_backend", return_value=None):
        b, probe, caps = select_backend_with_introspection()

    assert b is None
    assert probe is None
    assert caps is None


def test_select_device_discovery_snapshot_returns_payload() -> None:
    from src.tray.app.backend import select_device_discovery_snapshot

    payload = {"candidates": [{"device_type": "lightbar"}]}

    with patch("src.tray.app.backend.collect_device_discovery", return_value=payload):
        assert select_device_discovery_snapshot() == payload


def test_select_device_discovery_snapshot_swallows_errors() -> None:
    from src.tray.app.backend import select_device_discovery_snapshot

    logger = MagicMock()

    with (
        patch("src.tray.app.backend.logging.getLogger", return_value=logger),
        patch("src.tray.app.backend.collect_device_discovery", side_effect=RuntimeError("boom")),
    ):
        assert select_device_discovery_snapshot() is None

    _assert_logged_debug_traceback(logger, "Tray device discovery snapshot collection failed")


def test_select_device_discovery_snapshot_propagates_unexpected_errors() -> None:
    from src.tray.app.backend import select_device_discovery_snapshot

    with patch(
        "src.tray.app.backend.collect_device_discovery",
        side_effect=AssertionError("unexpected discovery bug"),
    ):
        with pytest.raises(AssertionError, match="unexpected discovery bug"):
            select_device_discovery_snapshot()
