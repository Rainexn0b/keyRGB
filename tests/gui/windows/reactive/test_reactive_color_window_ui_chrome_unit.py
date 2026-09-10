"""Reactive window chrome: description, lifecycle, geometry, and focus."""

from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.theme import focus as theme_focus, metrics as theme_metrics
from keyrgb.gui.windows import reactive_color
from tests.gui.windows.reactive._reactive_ui_fakes import (
    _FakeRoot,
    _FakeWidget,
)


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
