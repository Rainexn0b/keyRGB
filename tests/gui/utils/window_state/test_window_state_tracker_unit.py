from __future__ import annotations

"""WindowGeometryTracker behavior."""

import json
from types import SimpleNamespace

from keyrgb.gui.utils.window_state import (
    WindowGeometry,
    WindowGeometryTracker,
    load_window_geometry,
    save_window_geometry,
    ui_state_path,
)
from tests.gui.utils.window_state._window_state_fakes import _FakeRoot


# --- tracker ------------------------------------------------------------------
def test_tracker_restore_applies_clamped_geometry() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=5000, height=5000, x=50, y=60)) is True
    root = _FakeRoot(screen=(1920, 1080))
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    assert tracker.restore() is True
    assert root.applied == [f"{int(1920 * 0.95)}x{int(1080 * 0.95)}+50+60"]


def test_tracker_restore_size_only_centers_on_current_screen() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600)) is True
    root = _FakeRoot(screen=(1920, 1080))
    assert WindowGeometryTracker(root, "settings", 460, 520).restore() is True
    assert root.applied == ["800x600+560+240"]


def test_tracker_restore_size_only_centers_clamped_dimensions_on_smaller_screen() -> None:
    assert save_window_geometry("support", WindowGeometry(width=800, height=600)) is True
    root = _FakeRoot(screen=(400, 300))
    assert WindowGeometryTracker(root, "support", 460, 520).restore() is True
    assert root.applied == ["380x285+10+7"]


def test_tracker_restore_falls_back_when_missing_or_offscreen() -> None:
    tracker = WindowGeometryTracker(_FakeRoot(), "settings", 460, 520)
    assert tracker.restore() is False

    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=9000, y=9000)) is True
    root = _FakeRoot()
    assert WindowGeometryTracker(root, "settings", 460, 520).restore() is False
    assert root.applied == []


def test_tracker_start_tracking_only_binds() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    tracker.start_tracking()
    assert root.bindings == [("<Configure>", tracker._on_configure, "+")]
    assert load_window_geometry("settings") is None
    assert root.scheduled == []


def test_tracker_ignores_bubbled_descendant_events() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    tracker.start_tracking()
    child = object()
    tracker._on_configure(SimpleNamespace(widget=child))
    assert root.scheduled == []
    tracker._on_configure(SimpleNamespace(widget=root))
    assert len(root.scheduled) == 1
    assert root.scheduled[0][0] == 500


def test_tracker_debounce_cancels_pending() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520, debounce_ms=500)
    tracker.start_tracking()
    tracker._on_configure(SimpleNamespace(widget=root))
    first_token = root.scheduled[0][2]
    tracker._on_configure(SimpleNamespace(widget=root))
    assert root.cancelled == [first_token]
    assert len(root.scheduled) == 1  # pending write replaced, not duplicated
    assert root.scheduled[0][0] == 500
    root.fire_pending()
    assert load_window_geometry("settings") == WindowGeometry(width=880, height=840, x=100, y=80)


def test_tracker_save_now_cancels_pending_and_writes() -> None:
    root = _FakeRoot(width=700, height=500, x=11, y=22)
    tracker = WindowGeometryTracker(root, "support", 460, 520)
    tracker.start_tracking()
    tracker._on_configure(SimpleNamespace(widget=root))
    token = root.scheduled[0][2]
    assert tracker.save_now() is True
    assert root.cancelled == [token]
    assert root.scheduled == []
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500, x=11, y=22)


def test_tracker_wayland_save_is_size_only(monkeypatch) -> None:
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    root = _FakeRoot(width=700, height=500, x=11, y=22)
    tracker = WindowGeometryTracker(root, "support", 460, 520)
    assert tracker.save_now() is True
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500)
    raw = json.loads(ui_state_path().read_text(encoding="utf-8"))
    assert raw["windows"]["support"] == {"width": 700, "height": 500}


def test_tracker_xdg_session_type_wayland_save_is_size_only(monkeypatch) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=5, y=6)) is True
    assert load_window_geometry("settings") == WindowGeometry(width=800, height=600)
