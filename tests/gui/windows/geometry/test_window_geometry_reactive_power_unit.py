"""Geometry-persistence tests for reactive and power-mode windows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.utils import window_state
from keyrgb.gui.windows import power_mode, reactive_color
from tests.gui.windows.geometry._geometry_fakes import (
    _delays,
    _FakeGeometryTracker,
    _FakeRoot,
    _FakeVar,
    _FakeWidget,
    _fire_after,
    _geometry_pass_scheduled,
)

# ---------------------------------------------------------------------------


def _build_reactive_gui(monkeypatch: pytest.MonkeyPatch, root: _FakeRoot):
    config = SimpleNamespace(
        reactive_use_manual_color=False,
        reactive_visual_mode="subtle",
        reactive_color=(12, 34, 56),
        reactive_brightness=14,
        brightness=14,
    )

    def _frame(parent=None, **kwargs):
        return _FakeWidget(**kwargs)

    class _StubWheel:
        def __init__(self, parent, **kwargs) -> None:
            self.parent = parent
            self.pack_calls: list[dict[str, object]] = []

        def pack(self, **kwargs) -> None:
            self.pack_calls.append(dict(kwargs))

        def set_brightness_percent(self, _pct: int) -> None:
            return None

    monkeypatch.setattr(reactive_color.tk, "Tk", lambda: root)
    monkeypatch.setattr(reactive_color.tk, "BooleanVar", _FakeVar)
    monkeypatch.setattr(reactive_color.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(reactive_color.ttk, "Frame", _frame)
    monkeypatch.setattr(reactive_color.ttk, "Label", _frame)
    monkeypatch.setattr(reactive_color.ttk, "Checkbutton", _frame)
    monkeypatch.setattr(reactive_color.ttk, "Separator", _frame)
    monkeypatch.setattr(reactive_color.ttk, "Scale", _frame)
    monkeypatch.setattr(reactive_color, "ColorWheel", _StubWheel)
    monkeypatch.setattr(reactive_color, "Config", lambda: config)
    monkeypatch.setattr(reactive_color, "select_backend", lambda: None)
    monkeypatch.setattr(reactive_color, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color, "WindowGeometryTracker", _FakeGeometryTracker)
    return reactive_color.ReactiveColorGUI()


def test_reactive_restored_geometry_wins_and_suppresses_fallback(monkeypatch) -> None:
    _FakeGeometryTracker.next_restore_result = True
    root = _FakeRoot()

    gui = _build_reactive_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.window_id == "reactive-color"
    assert (tracker.min_width, tracker.min_height) == (520, 720)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    assert root.geometry_calls == ["restored:reactive-color"]
    assert not _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    assert gui._geometry_restored is True


def test_reactive_missing_state_retains_exact_fallback(monkeypatch) -> None:
    root = _FakeRoot()

    gui = _build_reactive_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert len(root.geometry_calls) == 1
    assert "x" in root.geometry_calls[0]
    assert _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    _fire_after(root, 50)
    assert len(root.geometry_calls) == 2
    _fire_after(root, 60)
    assert tracker.start_tracking_calls == 1
    assert gui._geometry_restored is False


def test_reactive_close_saves_before_destroy(monkeypatch) -> None:
    root = _FakeRoot()
    gui = _build_reactive_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    gui._on_close()

    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1
    assert root.events == ["save", "destroy"]


def test_reactive_close_route_stays_wired_to_window_manager(monkeypatch) -> None:
    root = _FakeRoot()
    _build_reactive_gui(monkeypatch, root)

    protocols = dict(root.protocol_calls)
    assert "WM_DELETE_WINDOW" in protocols
    protocols["WM_DELETE_WINDOW"]()
    assert root.destroy_calls == 1


# ---------------------------------------------------------------------------
# Power Mode window


# ---------------------------------------------------------------------------


def _build_power_gui(monkeypatch: pytest.MonkeyPatch, root: _FakeRoot):
    config = SimpleNamespace(system_power_extreme_cap_khz=1_300_000)

    def _widget(parent=None, **kwargs):
        return _FakeWidget(**kwargs)

    monkeypatch.setattr(power_mode.tk, "Tk", lambda: root)
    monkeypatch.setattr(power_mode.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(power_mode.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(power_mode.ttk, "Frame", _widget)
    monkeypatch.setattr(power_mode.ttk, "LabelFrame", _widget)
    monkeypatch.setattr(power_mode.ttk, "Label", _widget)
    monkeypatch.setattr(power_mode.ttk, "Button", _widget)
    monkeypatch.setattr(power_mode.ttk, "Scale", _widget)
    monkeypatch.setattr(power_mode, "Config", lambda: config)
    monkeypatch.setattr(power_mode, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "schedule_initial_focus", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (1_025_000, 1_300_000))
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=False, reason="test", mode=None, identifiers={}),
    )
    monkeypatch.setattr(power_mode, "compute_centered_window_geometry", lambda *_args, **_kwargs: "centered-fallback")
    monkeypatch.setattr(power_mode, "WindowGeometryTracker", _FakeGeometryTracker)
    return power_mode.PowerModeSettingsGUI()


def test_power_restored_geometry_wins_and_suppresses_fallback(monkeypatch) -> None:
    _FakeGeometryTracker.next_restore_result = True
    root = _FakeRoot()

    gui = _build_power_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.window_id == "power-mode"
    assert (tracker.min_width, tracker.min_height) == (700, 460)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    assert root.geometry_calls == ["restored:power-mode"]
    assert not _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    assert gui._geometry_restored is True


def test_power_missing_state_retains_exact_fallback(monkeypatch) -> None:
    root = _FakeRoot()

    gui = _build_power_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert root.geometry_calls == ["centered-fallback"]
    assert _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    _fire_after(root, 50)
    assert root.geometry_calls == ["centered-fallback", "centered-fallback"]
    _fire_after(root, 60)
    assert tracker.start_tracking_calls == 1
    assert gui._geometry_restored is False


def test_power_malformed_state_falls_back_with_real_tracker(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    (tmp_path / "ui-state.json").write_text('{"windows": {"power-mode": "garbage"}}', encoding="utf-8")
    root = _FakeRoot()

    real_tracker = window_state.WindowGeometryTracker
    monkeypatch.setattr(power_mode, "WindowGeometryTracker", real_tracker)
    # Reuse the stubbed builder but keep the real tracker class.
    config = SimpleNamespace(system_power_extreme_cap_khz=1_300_000)

    def _widget(parent=None, **kwargs):
        return _FakeWidget(**kwargs)

    monkeypatch.setattr(power_mode.tk, "Tk", lambda: root)
    monkeypatch.setattr(power_mode.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(power_mode.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(power_mode.ttk, "Frame", _widget)
    monkeypatch.setattr(power_mode.ttk, "LabelFrame", _widget)
    monkeypatch.setattr(power_mode.ttk, "Label", _widget)
    monkeypatch.setattr(power_mode.ttk, "Button", _widget)
    monkeypatch.setattr(power_mode.ttk, "Scale", _widget)
    monkeypatch.setattr(power_mode, "Config", lambda: config)
    monkeypatch.setattr(power_mode, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "schedule_initial_focus", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (None, None))
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=False, reason="test", mode=None, identifiers={}),
    )
    monkeypatch.setattr(power_mode, "compute_centered_window_geometry", lambda *_args, **_kwargs: "centered-fallback")

    gui = power_mode.PowerModeSettingsGUI()

    assert gui._geometry_restored is False
    assert root.geometry_calls == ["centered-fallback"]
    assert _geometry_pass_scheduled(root, gui)


def test_power_close_saves_before_destroy_and_wires_wm_close(monkeypatch) -> None:
    root = _FakeRoot()
    gui = _build_power_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    protocols = dict(root.protocol_calls)
    assert protocols.get("WM_DELETE_WINDOW") == gui._close

    gui._close()

    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1
    assert root.events == ["save", "destroy"]


# ---------------------------------------------------------------------------
# Support Tools window
