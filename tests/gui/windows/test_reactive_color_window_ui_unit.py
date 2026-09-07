from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.windows import reactive_color


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
        self.kwargs.update(kwargs)

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 640))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 820))


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
        self.update_idletasks_calls = 0

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

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600

    def destroy(self) -> None:
        self.destroy_calls += 1


def test_build_description_section_syncs_wrap_for_existing_and_later_labels() -> None:
    root = _FakeRoot()
    main = _FakeWidget(width_px=640)
    created_labels: list[_FakeWidget] = []

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        created_labels.append(widget)
        return widget

    gui = SimpleNamespace(root=root, _wrap_labels=[])

    reactive_color.reactive_color_bootstrap.build_description_section(
        gui,
        main,
        ttk_module=SimpleNamespace(Label=_label),
        wrap_sync_errors=reactive_color._WRAP_SYNC_ERRORS,
    )

    later_label = _FakeWidget()
    gui._wrap_labels.append(later_label)
    main.bind_calls[0][1]()

    assert created_labels[0].configure_calls[-1] == {"wraplength": 616}
    assert later_label.configure_calls[-1] == {"wraplength": 616}


def test_install_lifecycle_bindings_handles_keyboard_interrupt_and_sigint() -> None:
    root = _FakeRoot()
    original_callback_calls: list[tuple[object, object, object]] = []
    root.report_callback_exception = lambda exc, val, tb: original_callback_calls.append((exc, val, tb))
    close_calls: list[str] = []
    signal_calls: list[tuple[int, object]] = []

    gui = SimpleNamespace(root=root, _on_close=lambda: close_calls.append("closed"))
    signal_module = SimpleNamespace(signal=lambda sig, handler: signal_calls.append((sig, handler)))

    reactive_color.reactive_color_bootstrap.install_lifecycle_bindings(
        gui,
        signal_module=signal_module,
        sigint=2,
    )

    assert [name for name, _callback in root.protocol_calls] == ["WM_DELETE_WINDOW"]

    runtime_error = RuntimeError("boom")
    root.report_callback_exception(RuntimeError, runtime_error, None)
    assert original_callback_calls == [(RuntimeError, runtime_error, None)]

    root.report_callback_exception(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert close_calls == ["closed"]

    signal_calls[0][1]()
    assert close_calls == ["closed", "closed"]


def test_apply_geometry_uses_requested_content_size(monkeypatch) -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.root = _FakeRoot()
    gui._main_frame = _FakeWidget(reqwidth_px=680, reqheight_px=910)
    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "680x954+10+20"

    monkeypatch.setattr(reactive_color, "compute_centered_window_geometry", _fake_compute)

    gui._apply_geometry()

    assert gui.root.update_idletasks_calls == 1
    assert seen == {
        "root": gui.root,
        "content_height_px": 910,
        "content_width_px": 680,
        "footer_height_px": 0,
        "chrome_padding_px": 44,
        "default_w": 629,
        "default_h": 940,
        "screen_ratio_cap": 0.95,
    }
    assert gui.root.geometry_calls == ["680x954+10+20"]


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


def test_on_toggle_reactive_visual_mode_persists_vivid_and_subtle() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_vivid_visuals_var = _FakeVar(True)
    gui.config = SimpleNamespace(reactive_visual_mode="subtle")

    gui._on_toggle_reactive_visual_mode()
    assert gui.config.reactive_visual_mode == "vivid"

    gui._reactive_vivid_visuals_var = _FakeVar(False)
    gui._on_toggle_reactive_visual_mode()
    assert gui.config.reactive_visual_mode == "subtle"


def test_read_reactive_trail_percent_returns_default_for_missing_attribute() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.config = SimpleNamespace()  # no reactive_trail_percent attribute

    result = gui._read_reactive_trail_percent()

    assert result == 40


def test_read_reactive_trail_percent_returns_clamped_values() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.config = SimpleNamespace(reactive_trail_percent=200)

    result = gui._read_reactive_trail_percent()

    assert result == 100


def test_sync_reactive_trail_widgets_keeps_defaults_when_config_is_invalid() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(40.0)
    gui._reactive_trail_label = _FakeLabel()
    gui._read_reactive_trail_percent = lambda: None

    gui._sync_reactive_trail_widgets()

    assert gui._reactive_trail_var.get() == 40.0
    assert gui._reactive_trail_label.config_calls == []


def test_on_reactive_trail_release_saves_and_sets_status() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(75.0)
    status_calls: list[dict] = []
    gui._set_status = lambda msg, ok: status_calls.append({"msg": msg, "ok": ok})
    committed: list[float] = []
    gui._commit_trail_to_config = lambda pct: committed.append(float(pct)) or round(float(pct))

    gui._on_reactive_trail_release()

    assert committed == [75.0]
    assert status_calls == [{"msg": "✓ Saved wave thickness 75%", "ok": True}]


def test_on_reactive_trail_release_reports_failure_when_commit_returns_none() -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui._reactive_trail_var = _FakeVar(40.0)
    status_calls: list[dict] = []
    gui._set_status = lambda msg, ok: status_calls.append({"msg": msg, "ok": ok})
    gui._commit_trail_to_config = lambda pct: None

    gui._on_reactive_trail_release()

    assert status_calls[0]["ok"] is False
