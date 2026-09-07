from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.windows import (
    _uniform_color_ui as uniform_color_ui,
    uniform,
)


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
        self.protocol_calls: list[tuple[str, object]] = []

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

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))


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
    monkeypatch.setattr(uniform, "acquire_hardware_control_lock", lambda: True)
    monkeypatch.setattr(uniform, "release_hardware_control_lock", lambda: None)

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
    assert [name for name, _callback in root.protocol_calls] == ["WM_DELETE_WINDOW"]


def test_constructor_delegates_bootstrap_state_to_adapter(monkeypatch) -> None:
    root = _FakeRoot()
    config = SimpleNamespace(color=(12, 34, 56), brightness=25, effect="none")
    calls: list[dict[str, object]] = []
    releases: list[bool] = []

    monkeypatch.setattr(uniform.tk, "Tk", lambda: root)
    monkeypatch.setattr(uniform, "Config", lambda: config)
    monkeypatch.setattr(uniform, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "compute_centered_window_geometry", lambda *_args, **_kwargs: "520x570+10+20")
    monkeypatch.setattr(uniform_color_ui, "build_uniform_window_ui", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(uniform, "acquire_hardware_control_lock", lambda: True)
    monkeypatch.setattr(uniform, "release_hardware_control_lock", lambda: releases.append(True))

    def _fake_init_adapter(**kwargs):
        calls.append(dict(kwargs))
        return uniform.uniform_init_adapter.UniformInitState(
            backend="backend",
            color_supported=False,
            device="device",
        )

    monkeypatch.setattr(uniform.uniform_init_adapter, "initialize_device_bootstrap_state", _fake_init_adapter)

    gui = uniform.UniformColorGUI()

    assert len(calls) == 1
    assert calls[0]["secondary_route"] is None
    assert calls[0]["requested_backend"] is None
    assert calls[0]["select_backend_fn"] is uniform.select_backend
    assert calls[0]["is_device_busy_fn"] is uniform.is_device_busy
    assert calls[0]["allow_hardware"] is True
    assert gui._backend == "backend"
    assert gui._color_supported is False
    assert gui.kb == "device"

    gui._on_close()
    assert releases == [True]


def test_on_close_releases_device_and_hardware_lock(monkeypatch) -> None:
    calls: list[str] = []
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.kb = SimpleNamespace(close=lambda: calls.append("device:close"))
    gui._owns_hardware_lock = True
    gui.root = SimpleNamespace(destroy=lambda: calls.append("root:destroy"))
    monkeypatch.setattr(uniform, "release_hardware_control_lock", lambda: calls.append("lock:release"))

    gui._on_close()

    assert calls == ["device:close", "lock:release", "root:destroy"]
    assert gui.kb is None
    assert gui._owns_hardware_lock is False


def test_build_uniform_window_ui_disables_apply_and_syncs_wrap_for_added_labels() -> None:
    root = _FakeRoot()
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

    gui = SimpleNamespace(
        root=root,
        _target_label="Keyboard",
        _color_supported=False,
        _initial_color=lambda: (_ for _ in ()).throw(AssertionError("unexpected initial color lookup")),
        _on_color_change=lambda *_args, **_kwargs: None,
        _on_color_release=lambda *_args, **_kwargs: None,
        _on_apply=lambda: None,
        _on_close=lambda: None,
    )

    uniform_color_ui.build_uniform_window_ui(
        gui,
        ttk_module=SimpleNamespace(Frame=_frame, Label=_label, Button=_button),
        color_wheel_cls=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected ColorWheel")),
        wrap_sync_errors=(RuntimeError,),
        tk_widget_state_errors=(RuntimeError,),
    )

    main_frame = registry["frames"][0]
    apply_button = registry["buttons"][0]
    extra_label = _FakeWidget(main_frame)
    gui._wrap_labels.append(extra_label)

    main_frame.bind_calls[0][1]()

    assert gui._main_frame is main_frame
    assert gui.color_wheel is None
    assert apply_button.configure_calls == [{"state": "disabled"}]
    assert gui._wrap_labels[0].configure_calls[-1] == {"wraplength": 536}
    assert extra_label.configure_calls == [{"wraplength": 536}]


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


def test_on_color_change_preserves_keyboard_effect_while_updating_base_color() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class _Config:
        effect = "wave"
        color = (1, 2, 3)

    gui.config = _Config()
    gui._target_is_secondary = False
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = 0.0

    gui._on_color_change(7, 8, 9)

    assert gui.config.effect == "wave"
    assert gui.config.color == (7, 8, 9)


def test_on_apply_preserves_keyboard_effect_when_apply_is_deferred() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    applied: list[tuple[int, int, int, int]] = []
    statuses: list[tuple[str, bool]] = []

    class _Config:
        effect = "wave"
        color = (1, 2, 3)
        brightness = 25

    gui._color_supported = True
    gui.config = _Config()
    gui._target_is_secondary = False
    gui.color_wheel = SimpleNamespace(get_color=lambda: (4, 5, 6))
    gui._target_label = "Keyboard"
    gui._apply_color = lambda r, g, b, brightness: applied.append((r, g, b, brightness)) or "deferred"
    gui._set_status = lambda msg, *, ok: statuses.append((msg, ok))

    gui._on_apply()

    assert gui.config.effect == "wave"
    assert gui.config.color == (4, 5, 6)
    assert applied == [(4, 5, 6, 25)]
    assert statuses == [("✓ Saved Keyboard RGB(4, 5, 6)", True)]


def test_on_color_release_preserves_keyboard_effect_and_reports_applied_status(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    applied: list[tuple[int, int, int, int]] = []
    statuses: list[tuple[str, bool]] = []

    class _Config:
        effect = "wave"
        color = (1, 2, 3)
        brightness = 40

    gui.config = _Config()
    gui._target_is_secondary = False
    gui._target_label = "Keyboard"
    gui._last_drag_committed_color = None
    gui._last_drag_commit_ts = 0.0
    gui._apply_color = lambda r, g, b, brightness: applied.append((r, g, b, brightness)) or True
    gui._set_status = lambda msg, *, ok: statuses.append((msg, ok))

    monkeypatch.setattr(uniform.time, "monotonic", lambda: 12.5)

    gui._on_color_release(7, 8, 9)

    assert gui.config.effect == "wave"
    assert gui.config.color == (7, 8, 9)
    assert applied == [(7, 8, 9, 40)]
    assert gui._last_drag_committed_color == (7, 8, 9)
    assert gui._last_drag_commit_ts == 12.5
    assert statuses == [("✓ Applied Keyboard RGB(7, 8, 9)", True)]
