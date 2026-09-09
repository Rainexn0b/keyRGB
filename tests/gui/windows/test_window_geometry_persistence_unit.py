"""Focused UX-06 geometry-persistence tests for uniform/reactive/power/support windows.

Each main window must restore persisted geometry before its centered
fallback passes, suppress those fallbacks when restoration wins, start
``<Configure>`` tracking only after the initial programmatic passes, and
save synchronously on every orderly close before cleanup/destruction.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest

from keyrgb.gui.utils import window_state
from keyrgb.gui.windows import power_mode, reactive_color, support, uniform


class _FakeGeometryTracker:
    """Stand-in for WindowGeometryTracker with per-test restore control."""

    next_restore_result = False
    instances: ClassVar[list[_FakeGeometryTracker]] = []

    def __init__(
        self,
        root,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> None:
        self.root = root
        self.window_id = window_id
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.screen_ratio_cap = float(screen_ratio_cap)
        self.restore_calls = 0
        self.start_tracking_calls = 0
        self.save_now_calls = 0
        type(self).instances.append(self)

    def restore(self) -> bool:
        self.restore_calls += 1
        if type(self).next_restore_result:
            self.root.geometry(f"restored:{self.window_id}")
            return True
        return False

    def start_tracking(self) -> None:
        self.start_tracking_calls += 1

    def save_now(self) -> bool:
        self.save_now_calls += 1
        events = getattr(self.root, "events", None)
        if events is not None:
            events.append("save")
        return True

    @classmethod
    def last(cls) -> _FakeGeometryTracker:
        assert cls.instances
        return cls.instances[-1]


@pytest.fixture(autouse=True)
def _reset_fake_tracker():
    _FakeGeometryTracker.instances.clear()
    _FakeGeometryTracker.next_restore_result = False
    yield
    _FakeGeometryTracker.instances.clear()
    _FakeGeometryTracker.next_restore_result = False


class _FakeVar:
    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, *args, **kwargs) -> None:
        return None

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def columnconfigure(self, *args, **kwargs) -> None:
        return None

    def rowconfigure(self, *args, **kwargs) -> None:
        return None

    def focus_set(self) -> None:
        return None

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", 640))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 520))

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 640))


class _FakeRoot:
    def __init__(self) -> None:
        self.geometry_calls: list[str] = []
        self.after_calls: list[tuple[int, object]] = []
        self.protocol_calls: list[tuple[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.title_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0
        self.events: list[str] = []
        self.report_callback_exception = lambda *_args: None

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, _width: bool, _height: bool) -> None:
        return None

    def after(self, delay: int, callback):
        self.after_calls.append((int(delay), callback))
        return f"after-{len(self.after_calls)}"

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def focus_get(self):
        return None

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def destroy(self) -> None:
        self.destroy_calls += 1
        self.events.append("destroy")


def _fire_after(root: _FakeRoot, delay: int) -> int:
    fired = 0
    for scheduled_delay, callback in list(root.after_calls):
        if scheduled_delay == delay:
            callback()
            fired += 1
    return fired


def _delays(root: _FakeRoot) -> list[int]:
    return [delay for delay, _callback in root.after_calls]


def _geometry_pass_scheduled(root: _FakeRoot, gui) -> bool:
    """Delay 50 is shared with initial-focus callbacks; match by identity."""
    return any(delay == 50 and callback == gui._apply_geometry for delay, callback in root.after_calls)


# ---------------------------------------------------------------------------
# Uniform Color window
# ---------------------------------------------------------------------------


def _build_uniform_gui(monkeypatch: pytest.MonkeyPatch, root: _FakeRoot):
    def _stub_build_ui(gui, **_kwargs) -> None:
        gui._main_frame = _FakeWidget(reqwidth_px=480, reqheight_px=560)
        gui._apply_button = object()
        gui._close_button = object()
        gui.color_wheel = None

    monkeypatch.setattr(uniform.tk, "Tk", lambda: root)
    monkeypatch.setattr(uniform, "Config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        uniform.uniform_init_adapter,
        "initialize_device_bootstrap_state",
        lambda **_kwargs: SimpleNamespace(backend=None, color_supported=False, device=None),
    )
    monkeypatch.setattr(uniform.uniform_color_ui, "build_uniform_window_ui", _stub_build_ui)
    monkeypatch.setattr(uniform.uniform_color_state, "initialize_drag_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "schedule_initial_focus", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "WindowGeometryTracker", _FakeGeometryTracker)
    monkeypatch.setenv("KEYRGB_TRAY_MANAGED_GUI", "1")
    return uniform.UniformColorGUI()


def test_uniform_restored_geometry_wins_and_suppresses_fallback(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    _FakeGeometryTracker.next_restore_result = True
    root = _FakeRoot()

    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.window_id == "uniform-keyboard"
    assert (tracker.min_width, tracker.min_height) == (460, 520)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    assert tracker.restore_calls == 1
    assert root.geometry_calls == ["restored:uniform-keyboard"]
    # Both centered passes (immediate + delayed) are suppressed ...
    assert not _geometry_pass_scheduled(root, gui)
    # ... while tracking is still scheduled just after the last pass.
    assert 60 in _delays(root)
    assert tracker.start_tracking_calls == 0
    assert gui._geometry_restored is True


def test_uniform_missing_state_retains_exact_fallback(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    root = _FakeRoot()

    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    assert tracker.restore_calls == 1
    assert len(root.geometry_calls) == 1
    assert root.geometry_calls[0].startswith("520x610+") or "x" in root.geometry_calls[0]
    assert _geometry_pass_scheduled(root, gui)
    assert 60 in _delays(root)
    # Tracking starts only after the initial passes fire.
    assert tracker.start_tracking_calls == 0
    _fire_after(root, 50)
    assert len(root.geometry_calls) == 2
    _fire_after(root, 60)
    assert tracker.start_tracking_calls == 1
    assert gui._geometry_restored is False


def test_uniform_dynamic_route_ids_stay_isolated(monkeypatch) -> None:
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)

    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    _build_uniform_gui(monkeypatch, _FakeRoot())
    keyboard_id = _FakeGeometryTracker.last().window_id

    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "lightbar")
    _build_uniform_gui(monkeypatch, _FakeRoot())
    lightbar_id = _FakeGeometryTracker.last().window_id

    assert keyboard_id == "uniform-keyboard"
    assert lightbar_id == "uniform-lightbar"
    assert keyboard_id != lightbar_id
    assert uniform.uniform_instance_identity(target_context="keyboard") == keyboard_id
    assert uniform.uniform_instance_identity(target_context="lightbar") == lightbar_id


def test_uniform_storage_isolation_per_route(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    assert (
        window_state.save_window_geometry(
            "uniform-keyboard", window_state.WindowGeometry(width=800, height=600, x=10, y=20)
        )
        is True
    )
    assert window_state.load_window_geometry("uniform-lightbar") is None
    assert window_state.load_window_geometry("uniform-keyboard") == window_state.WindowGeometry(
        width=800, height=600, x=10, y=20
    )


def test_uniform_close_saves_before_hardware_cleanup_and_destroy(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    monkeypatch.delenv("KEYRGB_UNIFORM_BACKEND", raising=False)
    root = _FakeRoot()
    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()

    class _FakeDevice:
        def close(self) -> None:
            root.events.append("device-close")

    gui.kb = _FakeDevice()
    assert dict(root.protocol_calls).get("WM_DELETE_WINDOW") == gui._on_close
    gui._on_close()

    assert tracker.save_now_calls == 1
    assert root.destroy_calls == 1
    assert root.events == ["save", "device-close", "destroy"]


def test_uniform_unexpected_geometry_save_error_still_cleans_up(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    root = _FakeRoot()
    gui = _build_uniform_gui(monkeypatch, root)
    tracker = _FakeGeometryTracker.last()
    tracker.save_now = lambda: (_ for _ in ()).throw(RuntimeError("save failed"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="save failed"):
        gui._on_close()

    assert root.destroy_calls == 1


# ---------------------------------------------------------------------------
# Reactive Color window
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
