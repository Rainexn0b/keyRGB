"""Geometry-persistence tests for the Support Tools window."""

from __future__ import annotations

import pytest

from keyrgb.gui.windows import support
from tests.gui.windows.geometry._geometry_fakes import (
    _delays,
    _FakeGeometryTracker,
    _FakeRoot,
    _FakeWidget,
    _fire_after,
    _geometry_pass_scheduled,
)

# ---------------------------------------------------------------------------


def _build_support_gui(monkeypatch: pytest.MonkeyPatch, root: _FakeRoot):
    class _FakeStyle:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def configure(self, *args, **kwargs) -> None:
            return None

        def map(self, *args, **kwargs) -> None:
            return None

    class _ConstructText(_FakeWidget):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(**kwargs)

        def delete(self, *args, **kwargs) -> None:
            return None

        def insert(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(support.tk, "Tk", lambda: root)
    monkeypatch.setattr(support.ttk, "Frame", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support.ttk, "Label", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support.ttk, "LabelFrame", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support.ttk, "Button", lambda *args, **kwargs: _FakeWidget(**kwargs))
    monkeypatch.setattr(support.ttk, "Style", lambda *args, **kwargs: _FakeStyle(*args, **kwargs))
    monkeypatch.setattr(support.scrolledtext, "ScrolledText", lambda *args, **kwargs: _ConstructText(*args, **kwargs))
    monkeypatch.setattr(support, "apply_keyrgb_window_icon", lambda root: None)
    monkeypatch.setattr(support, "apply_clam_theme", lambda root, **kwargs: ("#111111", "#eeeeee"))
    monkeypatch.setattr(support, "WindowGeometryTracker", _FakeGeometryTracker)
    return support.SupportToolsGUI()


def test_support_restored_geometry_wins_and_suppresses_delayed_fallback(monkeypatch) -> None:
    _FakeGeometryTracker.next_restore_result = True
    root = _FakeRoot()
    center_calls: list[object] = []
    monkeypatch.setattr(support, "center_window_on_screen", lambda window: center_calls.append(window))

    gui = _build_support_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.window_id == "support"
    assert (tracker.min_width, tracker.min_height) == (960, 720)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    # The helper's immediate position-only centering still runs (out of scope
    # to change), but restore() re-applies the saved geometry over it and the
    # delayed full centered pass is suppressed.
    assert center_calls == [root]
    assert root.geometry_calls == ["restored:support"]
    assert not _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    assert gui._geometry_restored is True


def test_support_missing_state_retains_exact_fallback(monkeypatch) -> None:
    root = _FakeRoot()
    center_calls: list[object] = []
    monkeypatch.setattr(support, "center_window_on_screen", lambda window: center_calls.append(window))

    gui = _build_support_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert center_calls == [root]
    assert _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    _fire_after(root, 60)
    assert tracker.start_tracking_calls == 1
    assert gui._geometry_restored is False


def test_support_close_saves_before_destroy_and_wires_wm_close(monkeypatch) -> None:
    root = _FakeRoot()
    monkeypatch.setattr(support, "center_window_on_screen", lambda window: None)
    gui = _build_support_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    protocols = dict(root.protocol_calls)
    assert protocols.get("WM_DELETE_WINDOW") == gui._on_close

    gui._on_close()

    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1
    assert root.events == ["save", "destroy"]
