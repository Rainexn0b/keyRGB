from __future__ import annotations

from unittest.mock import MagicMock, patch


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


def test_select_backend_with_introspection_handles_probe_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.side_effect = RuntimeError("boom")
    backend.capabilities.return_value = "caps"

    with patch("src.tray.app.backend.select_backend", return_value=backend):
        b, probe, caps = select_backend_with_introspection()

    assert b is backend
    assert probe is None
    assert caps == "caps"


def test_select_backend_with_introspection_handles_caps_exception() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    backend = MagicMock()
    backend.probe.return_value = "probe"
    backend.capabilities.side_effect = RuntimeError("boom")

    with patch("src.tray.app.backend.select_backend", return_value=backend):
        b, probe, caps = select_backend_with_introspection()

    assert b is backend
    assert probe == "probe"
    assert caps is None


def test_select_backend_with_introspection_handles_none_backend() -> None:
    from src.tray.app.backend import select_backend_with_introspection

    with patch("src.tray.app.backend.select_backend", return_value=None):
        b, probe, caps = select_backend_with_introspection()

    assert b is None
    assert probe is None
    assert caps is None
