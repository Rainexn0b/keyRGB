from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.windows.uniform as uniform


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 560))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 640))


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600

    def destroy(self) -> None:
        self.destroy_calls += 1


class _FakeColorWheel:
    def __init__(self, parent, *, size: int, initial_color: tuple[int, int, int], callback, release_callback) -> None:
        self.parent = parent
        self.size = size
        self.initial_color = initial_color
        self.callback = callback
        self.release_callback = release_callback
        self.pack_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def get_color(self) -> tuple[int, int, int]:
        return self.initial_color


def test_probe_color_support_defaults_to_true_when_backend_capability_probe_fails() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise RuntimeError("boom")

    assert gui._probe_color_support(BrokenBackend()) is True


def test_probe_color_support_propagates_unexpected_capability_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._probe_color_support(BrokenBackend())


def test_select_backend_best_effort_propagates_unexpected_selection_failure(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.requested_backend = "sysfs-leds"

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    with pytest.raises(AssertionError):
        gui._select_backend_best_effort()


def test_select_backend_best_effort_uses_secondary_route_backend(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    sentinel = object()
    gui._secondary_route = SimpleNamespace(get_backend=lambda: sentinel)

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    assert gui._select_backend_best_effort() is sentinel


def test_acquire_device_best_effort_returns_none_when_device_is_busy(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    err = OSError("busy")

    class BusyBackend:
        def get_device(self):
            raise err

    monkeypatch.setattr(uniform, "is_device_busy", lambda exc: exc is err)

    assert gui._acquire_device_best_effort(BusyBackend()) is None


def test_acquire_device_best_effort_propagates_unexpected_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def get_device(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._acquire_device_best_effort(BrokenBackend())


def test_apply_color_returns_false_for_recoverable_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise RuntimeError("boom")

    gui.kb = BrokenKeyboard()

    assert gui._apply_color(1, 2, 3, 25) is False


def test_apply_color_propagates_unexpected_write_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise AssertionError("boom")

    gui.kb = BrokenKeyboard()

    with pytest.raises(AssertionError, match="boom"):
        gui._apply_color(1, 2, 3, 25)


def test_commit_color_to_config_uses_secondary_route_state(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    calls: list[tuple[str, tuple[int, int, int], str | None]] = []

    class _Config:
        effect = "wave"

        def set_secondary_device_color(self, state_key: str, color, *, compatibility_key=None, default=(255, 0, 0)):
            assert default == (255, 0, 0)
            calls.append((state_key, tuple(color), compatibility_key))

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)

    gui._commit_color_to_config(4, 5, 6)

    assert calls == [("mouse", (4, 5, 6), None)]
    assert gui.config.effect == "wave"


def test_constructor_uses_content_driven_geometry(monkeypatch) -> None:
    root = _FakeRoot()
    config = SimpleNamespace(color=(12, 34, 56), brightness=25, effect="none")
    registry: dict[str, list[_FakeWidget]] = {"frames": [], "labels": [], "buttons": []}

    def _frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["frames"].append(widget)
        return widget

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["buttons"].append(widget)
        return widget

    monkeypatch.setattr(uniform.tk, "Tk", lambda: root)
    monkeypatch.setattr(uniform.ttk, "Frame", _frame)
    monkeypatch.setattr(uniform.ttk, "Label", _label)
    monkeypatch.setattr(uniform.ttk, "Button", _button)
    monkeypatch.setattr(uniform, "ColorWheel", _FakeColorWheel)
    monkeypatch.setattr(uniform, "Config", lambda: config)
    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: None)
    monkeypatch.setattr(uniform, "route_for_backend_name", lambda _name: None)
    monkeypatch.setattr(uniform, "route_for_device_type", lambda _name: None)
    monkeypatch.setattr(uniform, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "compute_centered_window_geometry", lambda *_args, **_kwargs: "520x570+10+20")

    gui = uniform.UniformColorGUI()

    button_frame = registry["frames"][1]
    apply_button = registry["buttons"][0]
    close_button = registry["buttons"][1]

    assert root.title_calls == ["KeyRGB - Keyboard Color"]
    assert root.minsize_calls == [(460, 520)]
    assert root.geometry_calls == ["520x570+10+20"]
    assert any(delay == 50 for delay, _callback in root.after_calls)
    assert isinstance(gui.color_wheel, _FakeColorWheel)
    assert button_frame.columnconfigure_calls == [(0, 1), (1, 1)]
    assert apply_button.grid_calls == [{"row": 0, "column": 0, "sticky": "ew", "padx": (0, 8)}]
    assert close_button.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]


def test_apply_geometry_uses_requested_content_size(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.root = _FakeRoot()
    gui._main_frame = _FakeWidget(reqwidth_px=610, reqheight_px=700)
    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "610x740+10+20"

    monkeypatch.setattr(uniform, "compute_centered_window_geometry", _fake_compute)

    gui._apply_geometry()

    assert gui.root.update_idletasks_calls == 1
    assert seen == {
        "root": gui.root,
        "content_height_px": 700,
        "content_width_px": 610,
        "footer_height_px": 0,
        "chrome_padding_px": 40,
        "default_w": 520,
        "default_h": 610,
        "screen_ratio_cap": 0.95,
    }
    assert gui.root.geometry_calls == ["610x740+10+20"]


def test_on_color_change_updates_secondary_color_without_touching_keyboard_effect() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    stored: list[tuple[int, int, int]] = []

    class _Config:
        effect = "wave"
        color = (9, 9, 9)

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)
    gui._store_secondary_color = lambda color: stored.append(tuple(color))
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = 0.0

    gui._on_color_change(7, 8, 9)

    assert stored == [(7, 8, 9)]
    assert gui.config.effect == "wave"
    assert gui.config.color == (9, 9, 9)
