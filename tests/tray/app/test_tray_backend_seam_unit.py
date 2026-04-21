"""Integration seam tests for src/tray/app/backend.py.

Tests cover the three public functions:
- load_ite_dimensions()
- select_backend_with_introspection()
- select_device_discovery_snapshot()
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS
import src.tray.app.backend as _mod


# ---------------------------------------------------------------------------
# load_ite_dimensions
# ---------------------------------------------------------------------------


def test_load_ite_dimensions_no_backend_returns_reference_defaults():
    with patch.object(_mod, "select_backend", return_value=None):
        rows, cols = _mod.load_ite_dimensions()
    assert rows == REFERENCE_MATRIX_ROWS
    assert cols == REFERENCE_MATRIX_COLS


def test_load_ite_dimensions_backend_returns_dimensions():
    fake_backend = SimpleNamespace(dimensions=lambda: (8, 22))
    with patch.object(_mod, "select_backend", return_value=fake_backend):
        rows, cols = _mod.load_ite_dimensions()
    assert rows == 8
    assert cols == 22
    assert isinstance(rows, int)
    assert isinstance(cols, int)


def test_load_ite_dimensions_backend_raises_runtime_error_returns_reference_defaults():
    def _raise_dims():
        raise RuntimeError("device error")

    fake_backend = SimpleNamespace(dimensions=_raise_dims)
    with patch.object(_mod, "select_backend", return_value=fake_backend):
        rows, cols = _mod.load_ite_dimensions()
    assert rows == REFERENCE_MATRIX_ROWS
    assert cols == REFERENCE_MATRIX_COLS


# ---------------------------------------------------------------------------
# select_backend_with_introspection
# ---------------------------------------------------------------------------


def test_select_backend_with_introspection_no_backend_returns_triple_none():
    with patch.object(_mod, "select_backend", return_value=None):
        backend, probe, caps = _mod.select_backend_with_introspection()
    assert backend is None
    assert probe is None
    assert caps is None


def test_select_backend_with_introspection_working_backend_returns_all_non_none():
    fake_probe = SimpleNamespace(available=True, reason="ok", confidence=90)
    fake_caps = SimpleNamespace(per_key=True)
    fake_backend = SimpleNamespace(
        probe=lambda: fake_probe,
        capabilities=lambda: fake_caps,
    )
    with patch.object(_mod, "select_backend", return_value=fake_backend):
        backend, probe, caps = _mod.select_backend_with_introspection()
    assert backend is fake_backend
    assert probe is fake_probe
    assert caps is fake_caps


def test_select_backend_with_introspection_probe_raises_returns_none_probe():
    def _raise_probe():
        raise RuntimeError("probe failed")

    fake_caps = SimpleNamespace(per_key=False)
    fake_backend = SimpleNamespace(
        probe=_raise_probe,
        capabilities=lambda: fake_caps,
    )
    with patch.object(_mod, "select_backend", return_value=fake_backend):
        backend, probe, caps = _mod.select_backend_with_introspection()
    assert backend is fake_backend
    assert probe is None
    assert caps is fake_caps


def test_select_backend_with_introspection_no_probe_attribute_returns_none_probe():
    fake_caps = SimpleNamespace(per_key=True)
    # no 'probe' attribute on the namespace
    fake_backend = SimpleNamespace(capabilities=lambda: fake_caps)
    with patch.object(_mod, "select_backend", return_value=fake_backend):
        backend, probe, caps = _mod.select_backend_with_introspection()
    assert backend is fake_backend
    assert probe is None
    assert caps is fake_caps


# ---------------------------------------------------------------------------
# select_device_discovery_snapshot
# ---------------------------------------------------------------------------


def test_select_device_discovery_snapshot_returns_dict():
    expected = {"usb_devices": [], "sysfs_leds": []}
    with patch.object(_mod, "collect_device_discovery", return_value=expected):
        result = _mod.select_device_discovery_snapshot()
    assert result == expected


def test_select_device_discovery_snapshot_collector_raises_os_error_returns_none():
    def _raise():
        raise OSError("permission denied")

    with patch.object(_mod, "collect_device_discovery", side_effect=_raise):
        result = _mod.select_device_discovery_snapshot()
    assert result is None
