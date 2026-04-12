from __future__ import annotations

import logging

import pytest
from unittest.mock import MagicMock, patch

from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


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
    logger.log.assert_called_once_with(logging.DEBUG, "Falling back to default keyboard dimensions", exc_info=True)


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
    logger.log.assert_called_once_with(logging.DEBUG, "Backend probe failed during tray introspection", exc_info=True)


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
    logger.log.assert_called_once_with(
        logging.DEBUG, "Backend capabilities lookup failed during tray introspection", exc_info=True
    )


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

    logger.log.assert_called_once_with(logging.DEBUG, "Tray device discovery snapshot collection failed", exc_info=True)


def test_select_device_discovery_snapshot_propagates_unexpected_errors() -> None:
    from src.tray.app.backend import select_device_discovery_snapshot

    with patch(
        "src.tray.app.backend.collect_device_discovery",
        side_effect=AssertionError("unexpected discovery bug"),
    ):
        with pytest.raises(AssertionError, match="unexpected discovery bug"):
            select_device_discovery_snapshot()
