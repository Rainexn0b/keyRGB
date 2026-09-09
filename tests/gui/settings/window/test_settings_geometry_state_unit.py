"""UX-06 geometry persistence wiring for the settings window."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.settings.window as settings_window
from tests.gui.settings.window._settings_window_fakes import (
    _FakeGeometryTracker,
    _FakeRoot,
    _FakeScrollArea,
    _FakeWidget,
    _values,
)


@pytest.fixture
def _isolated_ui_state(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    return tmp_path


class _ScreenRoot(_FakeRoot):
    """Fake root that also reports a screen size for real-tracker restore."""

    def __init__(self, *, screen: tuple[int, int] = (1920, 1080)) -> None:
        super().__init__()
        self._screen = screen

    def winfo_screenwidth(self) -> int:
        return self._screen[0]

    def winfo_screenheight(self) -> int:
        return self._screen[1]


class _OrderRoot(_FakeRoot):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events

    def destroy(self) -> None:
        self._events.append("destroy")
        super().destroy()


def _fallback_gui(root: _FakeRoot, tracker: _FakeGeometryTracker) -> settings_window.PowerSettingsGUI:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = root
    gui._geometry_tracker = tracker
    gui.scroll_areas = {"lighting_power": _FakeScrollArea(None, bg_color="#000", padding=10)}
    gui.bottom_bar = _FakeWidget()
    gui._apply_enabled_state = lambda: None
    return gui


def _mocked_init(
    monkeypatch: pytest.MonkeyPatch, root: _FakeRoot
) -> tuple[settings_window.PowerSettingsGUI, dict[str, object]]:
    """Run the real __init__ with side-effecting steps stubbed; capture tracker args."""
    created: dict[str, object] = {}
    values = _values()

    def _factory(
        tracker_root, window_id: str, min_width: int, min_height: int, screen_ratio_cap: float = 0.95
    ) -> _FakeGeometryTracker:
        created.update(
            {
                "root": tracker_root,
                "window_id": window_id,
                "min_width": min_width,
                "min_height": min_height,
                "screen_ratio_cap": screen_ratio_cap,
            }
        )
        return _FakeGeometryTracker(tracker_root, window_id, min_width, min_height, screen_ratio_cap)

    monkeypatch.setattr(settings_window, "WindowGeometryTracker", _factory)
    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings_window, "apply_keyrgb_window_icon", lambda actual_root: None)
    monkeypatch.setattr(settings_window, "apply_clam_theme", lambda actual_root, **kwargs: ("#111", "#eee"))
    monkeypatch.setattr(settings_window, "Config", lambda: "config-obj")
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: True)
    monkeypatch.setattr(settings_window, "load_settings_values", lambda **kwargs: values)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_layout", lambda self, **kwargs: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_vars", lambda self, values: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: None)
    gui = settings_window.PowerSettingsGUI()
    return gui, created


def test_init_wires_settings_identity_minimum_and_ratio_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    gui, created = _mocked_init(monkeypatch, root)
    assert created["root"] is root
    assert created["window_id"] == "settings"
    assert (created["min_width"], created["min_height"]) == (680, 560)
    assert created["screen_ratio_cap"] == 0.95
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._on_close)]


def test_restored_state_suppresses_fallback_centering() -> None:
    root = _FakeRoot()
    tracker = _FakeGeometryTracker(root, "settings", 680, 560, 0.95, restore_result=True)
    gui = _fallback_gui(root, tracker)
    applied: list[str] = []
    gui._apply_geometry = lambda: applied.append("geometry")
    gui._finalize_layout()
    # The restored geometry wins: no immediate default map and none of the
    # 50/350ms centering passes run.
    assert tracker.restore_calls == 1
    assert gui._geometry_restored is True
    assert root.geometry_calls == []
    assert applied == []
    assert root.after_calls == [(400, tracker.start_tracking)]
    # Tracking itself is deferred: nothing is bound during startup.
    assert tracker.start_tracking_calls == 0
    assert root.bind_calls == []


def test_fallback_schedule_defers_tracking_until_after_final_pass() -> None:
    root = _FakeRoot()
    tracker = _FakeGeometryTracker(root, "settings", 680, 560, 0.95, restore_result=False)
    gui = _fallback_gui(root, tracker)
    applied: list[str] = []
    gui._apply_geometry = lambda: applied.append("geometry")
    gui._finalize_layout()
    assert gui._geometry_restored is False
    assert root.geometry_calls == ["880x840"]
    assert [delay for delay, _callback in root.after_calls] == [50, 350, 400]
    assert tracker.start_tracking_calls == 0
    by_delay = dict(root.after_calls)
    by_delay[50]()
    by_delay[350]()
    assert applied == ["geometry", "geometry"]
    assert tracker.start_tracking_calls == 0
    by_delay[400]()
    assert tracker.start_tracking_calls == 1


@pytest.mark.parametrize("state", ["missing", "corrupt"])
def test_missing_or_corrupt_state_retains_fallback_schedule(_isolated_ui_state, state: str, tmp_path) -> None:
    if state == "corrupt":
        (tmp_path / "ui-state.json").write_text("{not valid json", encoding="utf-8")
    root = _FakeRoot()
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = root
    gui._geometry_tracker = settings_window.WindowGeometryTracker(root, "settings", 680, 560, 0.95)
    gui.scroll_areas = {"lighting_power": _FakeScrollArea(None, bg_color="#000", padding=10)}
    gui.bottom_bar = _FakeWidget()
    gui._apply_enabled_state = lambda: None
    applied: list[str] = []
    gui._apply_geometry = lambda: applied.append("geometry")
    gui._finalize_layout()
    assert gui._geometry_restored is False
    assert root.geometry_calls == ["880x840"]
    assert [delay for delay, _callback in root.after_calls] == [50, 350, 400]


def test_real_tracker_restore_applies_clamped_geometry_and_suppresses_fallback(
    _isolated_ui_state,
) -> None:
    from keyrgb.gui.utils.window_state import WindowGeometry, save_window_geometry

    assert save_window_geometry("settings", WindowGeometry(width=5000, height=5000, x=50, y=60)) is True
    root = _ScreenRoot(screen=(1920, 1080))
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = root
    gui._geometry_tracker = settings_window.WindowGeometryTracker(root, "settings", 680, 560, 0.95)
    gui.scroll_areas = {"lighting_power": _FakeScrollArea(None, bg_color="#000", padding=10)}
    gui.bottom_bar = _FakeWidget()
    gui._apply_enabled_state = lambda: None
    applied: list[str] = []
    gui._apply_geometry = lambda: applied.append("geometry")
    gui._finalize_layout()
    assert gui._geometry_restored is True
    # Oversized entry is clamped to the current 0.95 screen cap; no fallback.
    assert root.geometry_calls == [f"{int(1920 * 0.95)}x{int(1080 * 0.95)}+50+60"]
    assert applied == []
    assert [delay for delay, _callback in root.after_calls] == [400]


def test_on_close_saves_geometry_before_destroy() -> None:
    events: list[str] = []
    root = _OrderRoot(events)
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = root
    tracker = _FakeGeometryTracker(root, "settings", 680, 560, 0.95, events=events)
    gui._geometry_tracker = tracker
    gui._on_close()
    assert events == ["save_now", "destroy"]
    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1


def test_on_close_without_tracker_still_destroys() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._on_close()
    assert gui.root.destroy_calls == 1


def test_unexpected_geometry_save_error_still_destroys() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._geometry_tracker = SimpleNamespace(save_now=lambda: (_ for _ in ()).throw(KeyboardInterrupt()))

    with pytest.raises(KeyboardInterrupt):
        gui._on_close()

    assert gui.root.destroy_calls == 1
