from __future__ import annotations

from types import SimpleNamespace

import src.gui.windows.reactive_color as reactive_color


class _FakeVar:
    def __init__(self, value) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.set_calls.append(value)
        self.value = value


class _FakeLabel:
    def __init__(self) -> None:
        self.config_calls: list[dict[str, object]] = []

    def config(self, **kwargs) -> None:
        self.config_calls.append(dict(kwargs))


class _FakeColorWheel:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def set_brightness_percent(self, pct: int) -> None:
        self.calls.append(pct)


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.protocol_calls: list[tuple[str, object]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.destroy_calls = 0
        self.report_callback_exception = lambda *_args: None

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600

    def destroy(self) -> None:
        self.destroy_calls += 1


class _FakeTkModule:
    class TclError(Exception):
        pass


class _FakeColorWheelWithCallback:
    def __init__(
        self,
        parent,
        *,
        size: int,
        initial_color: tuple[int, int, int],
        callback,
        release_callback,
        show_brightness_slider: bool,
    ) -> None:
        self.parent = parent
        self.size = size
        self.initial_color = initial_color
        self.callback = callback
        self.release_callback = release_callback
        self.show_brightness_slider = show_brightness_slider
        self.brightness_calls: list[int] = []
        self.pack_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def set_brightness_percent(self, pct: int) -> None:
        self.brightness_calls.append(pct)
        if self.callback is not None:
            self.callback(
                *self.initial_color,
                source="brightness",
                brightness_percent=float(pct),
            )


def test_read_reactive_brightness_percent_returns_none_for_invalid_config_value() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.config = SimpleNamespace(reactive_brightness="bad", brightness=17)

    assert gui._read_reactive_brightness_percent() is None


def test_sync_reactive_brightness_widgets_keeps_existing_defaults_when_config_is_invalid() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_brightness_var = _FakeVar(100.0)
    gui._reactive_brightness_label = _FakeLabel()
    gui._read_reactive_brightness_percent = lambda: None

    gui._sync_reactive_brightness_widgets()

    assert gui._reactive_brightness_var.get() == 100.0
    assert gui._reactive_brightness_label.config_calls == []


def test_sync_color_wheel_brightness_skips_missing_wheel_without_reading_config() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.color_wheel = None
    gui._use_manual_var = _FakeVar(False)
    gui._read_reactive_brightness_percent = lambda: (_ for _ in ()).throw(AssertionError("should not be called"))

    gui._sync_color_wheel_brightness()


def test_sync_color_wheel_brightness_applies_percent_when_manual_mode_is_disabled() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.color_wheel = _FakeColorWheel()
    gui._use_manual_var = _FakeVar(False)
    gui._read_reactive_brightness_percent = lambda: 28

    gui._sync_color_wheel_brightness()

    assert gui.color_wheel.calls == [28]


def test_constructor_handles_programmatic_brightness_sync_callback(monkeypatch) -> None:
    root = _FakeRoot()
    config = SimpleNamespace(
        reactive_use_manual_color=False,
        reactive_color=(12, 34, 56),
        reactive_brightness=14,
        brightness=14,
    )

    monkeypatch.setattr(reactive_color.tk, "Tk", lambda: root)
    monkeypatch.setattr(reactive_color.tk, "BooleanVar", _FakeVar)
    monkeypatch.setattr(reactive_color.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(reactive_color.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(reactive_color.ttk, "Label", _FakeWidget)
    monkeypatch.setattr(reactive_color.ttk, "Checkbutton", _FakeWidget)
    monkeypatch.setattr(reactive_color.ttk, "Separator", _FakeWidget)
    monkeypatch.setattr(reactive_color.ttk, "Scale", _FakeWidget)
    monkeypatch.setattr(reactive_color, "ColorWheel", _FakeColorWheelWithCallback)
    monkeypatch.setattr(reactive_color, "Config", lambda: config)
    monkeypatch.setattr(reactive_color, "select_backend", lambda: None)
    monkeypatch.setattr(reactive_color, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color, "center_window_on_screen", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reactive_color.time, "monotonic", lambda: 0.0)

    gui = reactive_color.ReactiveColorGUI()

    assert gui.color_wheel.brightness_calls == [28]
    assert gui._last_drag_commit_ts == 0.0
    assert gui._last_drag_committed_color is None
    assert gui._last_drag_committed_brightness is None
    assert config.reactive_use_manual_color is False
    assert config.reactive_color == (12, 34, 56)


def test_on_color_change_tolerates_missing_drag_state(monkeypatch) -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._color_supported = True
    committed: list[tuple[int, int, int]] = []
    gui._commit_color_to_config = lambda color: committed.append(color)
    monkeypatch.setattr(reactive_color.time, "monotonic", lambda: 10.0)

    gui._on_color_change(1, 2, 3)

    assert committed == [(1, 2, 3)]
    assert gui._last_drag_committed_color == (1, 2, 3)
    assert gui._last_drag_commit_ts == 10.0


def test_on_color_change_ignores_brightness_origin_callbacks(monkeypatch) -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._color_supported = True
    committed: list[tuple[int, int, int]] = []
    gui._commit_color_to_config = lambda color: committed.append(color)
    monkeypatch.setattr(reactive_color.time, "monotonic", lambda: 10.0)

    gui._on_color_change(1, 2, 3, source="brightness", brightness_percent=28.0)

    assert committed == []
    assert not hasattr(gui, "_last_drag_committed_color")


def test_on_reactive_brightness_change_tolerates_missing_drag_state(monkeypatch) -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_brightness_label = _FakeLabel()
    gui.color_wheel = _FakeColorWheel()
    gui._use_manual_var = _FakeVar(False)
    committed: list[float] = []
    gui._commit_brightness_to_config = lambda pct: committed.append(float(pct)) or 14
    monkeypatch.setattr(reactive_color.time, "monotonic", lambda: 20.0)

    gui._on_reactive_brightness_change("28")

    assert committed == [28.0]
    assert gui.color_wheel.calls == [28]
    assert gui._last_drag_commit_ts == 20.0
    assert gui._last_drag_committed_brightness == 28


def test_read_reactive_trail_percent_returns_default_for_missing_attribute() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.config = SimpleNamespace()  # no reactive_trail_percent attribute

    result = gui._read_reactive_trail_percent()

    assert result == 50


def test_read_reactive_trail_percent_returns_clamped_values() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.config = SimpleNamespace(reactive_trail_percent=200)

    result = gui._read_reactive_trail_percent()

    assert result == 100


def test_sync_reactive_trail_widgets_keeps_defaults_when_config_is_invalid() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(50.0)
    gui._reactive_trail_label = _FakeLabel()
    gui._read_reactive_trail_percent = lambda: None

    gui._sync_reactive_trail_widgets()

    assert gui._reactive_trail_var.get() == 50.0
    assert gui._reactive_trail_label.config_calls == []


def test_on_reactive_trail_release_saves_and_sets_status() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(75.0)
    status_calls: list[dict] = []
    gui._set_status = lambda msg, ok: status_calls.append({"msg": msg, "ok": ok})
    committed: list[float] = []
    gui._commit_trail_to_config = lambda pct: committed.append(float(pct)) or int(round(float(pct)))

    gui._on_reactive_trail_release()

    assert committed == [75.0]
    assert status_calls == [{"msg": "✓ Saved wave thickness 75%", "ok": True}]


def test_on_reactive_trail_release_reports_failure_when_commit_returns_none() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(50.0)
    status_calls: list[dict] = []
    gui._set_status = lambda msg, ok: status_calls.append({"msg": msg, "ok": ok})
    gui._commit_trail_to_config = lambda pct: None

    gui._on_reactive_trail_release()

    assert status_calls[0]["ok"] is False
