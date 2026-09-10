"""Autouse reset for geometry-persistence fake trackers."""

from __future__ import annotations

import pytest

from tests.gui.windows.geometry._geometry_fakes import _FakeGeometryTracker


@pytest.fixture(autouse=True)
def _reset_fake_tracker():
    _FakeGeometryTracker.instances.clear()
    _FakeGeometryTracker.next_restore_result = False
    yield
    _FakeGeometryTracker.instances.clear()
    _FakeGeometryTracker.next_restore_result = False
