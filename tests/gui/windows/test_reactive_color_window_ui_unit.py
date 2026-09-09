from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.theme import focus as theme_focus, metrics as theme_metrics
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
        self.focus_calls = 0

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.kwargs.update(kwargs)

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def focus_set(self) -> None:
        self.focus_calls += 1

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 640))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 820))


class _FakeRoot:
    def __init__(self, *, focused: object = None) -> None:
        self._focused = focused
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.protocol_calls: list[tuple[str, object]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.bind_calls: list[tuple[str, object, object | None]] = []
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

    def focus_get(self) -> object:
        return self._focused

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))

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


def test_description_section_uses_body_style_and_section_gap() -> None:
    root = _FakeRoot()
    main = _FakeWidget(width_px=640)
    created: list[_FakeWidget] = []

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        created.append(widget)
        return widget

    gui = SimpleNamespace(root=root, _wrap_labels=[])

    reactive_color.reactive_color_bootstrap.build_description_section(
        gui,
        main,
        ttk_module=SimpleNamespace(Label=_label),
        wrap_sync_errors=reactive_color._WRAP_SYNC_ERRORS,
    )

    assert created[0].kwargs.get("style") == theme_metrics.BODY_LABEL_STYLE
    assert "font" not in created[0].kwargs
    assert created[0].pack_calls[0] == {"pady": (0, theme_metrics.SECTION_GAP_Y), "fill": "x"}


def test_reactive_window_ui_uses_theme_styles_and_gap_constants() -> None:
    from keyrgb.gui.windows import _reactive_color_ui as reactive_color_ui

    main = _FakeWidget(width_px=640)
    labels: list[_FakeWidget] = []
    checks: list[_FakeWidget] = []
    separators: list[_FakeWidget] = []
    committed: list[tuple[int, int, int]] = []

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        labels.append(widget)
        return widget

    def _checkbutton(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        checks.append(widget)
        return widget

    def _separator(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        separators.append(widget)
        return widget

    def _frame(parent=None, **kwargs):
        return _FakeWidget(parent, **kwargs)

    def _scale(parent=None, **kwargs):
        return _FakeWidget(parent, **kwargs)

    class _Wheel:
        def __init__(self, parent, **kwargs) -> None:
            self.parent = parent
            self.kwargs = kwargs
            self.pack_calls: list[dict[str, object]] = []

        def pack(self, **kwargs) -> None:
            self.pack_calls.append(dict(kwargs))

        def set_brightness_percent(self, _pct: int) -> None:
            return None

    gui = SimpleNamespace(
        config=SimpleNamespace(
            reactive_use_manual_color=False, reactive_visual_mode="subtle", reactive_color=(1, 2, 3)
        ),
        _color_supported=True,
        _wrap_labels=[],
        _on_toggle_manual=lambda: None,
        _on_toggle_reactive_visual_mode=lambda: None,
        _on_color_change=lambda *args, **kwargs: None,
        _on_color_release=lambda *args, **kwargs: None,
        _on_reactive_brightness_change=lambda value: None,
        _on_reactive_brightness_release=lambda _event=None: None,
        _on_reactive_trail_change=lambda value: None,
        _on_reactive_trail_release=lambda _event=None: None,
        _sync_reactive_brightness_widgets=lambda: committed.append((0, 0, 0)),
        _sync_color_wheel_brightness=lambda: None,
        _sync_reactive_trail_widgets=lambda: None,
    )

    reactive_color_ui.build_reactive_window_ui(
        gui,
        main,
        tk_module=SimpleNamespace(BooleanVar=_FakeVar, DoubleVar=_FakeVar),
        ttk_module=SimpleNamespace(
            Checkbutton=_checkbutton, Label=_label, Separator=_separator, Frame=_frame, Scale=_scale
        ),
        color_wheel_cls=_Wheel,
        wrap_sync_errors=(RuntimeError,),
        tk_error=RuntimeError,
    )

    assert checks[0].pack_calls[0] == {"anchor": "w", "pady": (0, theme_metrics.CONTROL_GAP_Y)}
    assert checks[1].pack_calls[0] == {"anchor": "w", "pady": (0, theme_metrics.SECTION_GAP_Y)}
    assert separators[0].pack_calls[0] == {"fill": "x", "pady": (18, theme_metrics.SECTION_GAP_Y)}
    assert gui.status_label.kwargs.get("style") == theme_metrics.STATUS_LABEL_STYLE
    assert "font" not in gui.status_label.kwargs
    for widget in (*labels, *checks):
        font = widget.kwargs.get("font")
        assert not (isinstance(font, tuple) and font and font[0] == "Sans"), widget.kwargs
    # The vivid-visuals check is the always-enabled meaningful focus target.
    assert gui._reactive_vivid_visuals_check is checks[1]


def test_reactive_window_ui_styles_unsupported_body_message() -> None:
    from keyrgb.gui.windows import _reactive_color_ui as reactive_color_ui

    main = _FakeWidget(width_px=640)
    labels: list[_FakeWidget] = []

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        labels.append(widget)
        return widget

    gui = SimpleNamespace(
        config=SimpleNamespace(reactive_use_manual_color=True, reactive_visual_mode="subtle", reactive_color=(1, 2, 3)),
        _color_supported=False,
        _wrap_labels=[],
        _on_toggle_manual=lambda: None,
        _on_toggle_reactive_visual_mode=lambda: None,
        _on_color_change=lambda *args, **kwargs: None,
        _on_color_release=lambda *args, **kwargs: None,
        _on_reactive_brightness_change=lambda value: None,
        _on_reactive_brightness_release=lambda _event=None: None,
        _on_reactive_trail_change=lambda value: None,
        _on_reactive_trail_release=lambda _event=None: None,
        _sync_reactive_brightness_widgets=lambda: None,
        _sync_color_wheel_brightness=lambda: None,
        _sync_reactive_trail_widgets=lambda: None,
    )

    reactive_color_ui.build_reactive_window_ui(
        gui,
        main,
        tk_module=SimpleNamespace(BooleanVar=_FakeVar, DoubleVar=_FakeVar),
        ttk_module=SimpleNamespace(
            Checkbutton=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Label=_label,
            Separator=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Frame=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Scale=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
        ),
        color_wheel_cls=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no wheel when unsupported")),
        wrap_sync_errors=(RuntimeError,),
        tk_error=RuntimeError,
    )

    assert gui.color_wheel is None
    unsupported = next(
        label for label in labels if "Reactive typing can still run" in str(label.kwargs.get("text", ""))
    )
    assert unsupported.kwargs.get("style") == theme_metrics.BODY_LABEL_STYLE
    assert "font" not in unsupported.kwargs


def test_schedule_initial_focus_targets_always_enabled_vivid_check(monkeypatch) -> None:
    gui = reactive_color.ReactiveColorGUI.__new__(reactive_color.ReactiveColorGUI)
    gui.root = _FakeRoot()
    vivid = _FakeWidget()
    gui._reactive_vivid_visuals_check = vivid
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(reactive_color, "schedule_initial_focus", lambda root, target: calls.append((root, target)))

    gui._schedule_initial_focus()

    assert calls == [(gui.root, vivid)]


def test_reactive_initial_focus_is_scheduled_non_forcing() -> None:
    root = _FakeRoot()
    vivid = _FakeWidget()
    reactive_color.schedule_initial_focus(root, vivid)

    focus_entries = [(delay, cb) for delay, cb in root.after_calls if delay == theme_focus.INITIAL_FOCUS_DELAY_MS]
    assert len(focus_entries) == 1
    focus_entries[0][1]()
    assert vivid.focus_calls == 1
