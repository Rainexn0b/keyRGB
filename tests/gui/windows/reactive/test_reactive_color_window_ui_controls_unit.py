"""Reactive window controls: color, brightness, trail, themed UI, and focus."""

from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.theme import metrics as theme_metrics
from keyrgb.gui.windows import reactive_color
from tests.gui.windows.reactive._reactive_ui_fakes import (
    _FakeColorWheel,
    _FakeLabel,
    _FakeVar,
    _FakeWidget,
)


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
