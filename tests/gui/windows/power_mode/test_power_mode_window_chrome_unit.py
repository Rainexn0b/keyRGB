"""Power-mode window construction, shortcuts, and refresh helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from keyrgb.gui.windows import power_mode
from tests.gui.windows.power_mode._power_mode_fakes import _FakeRoot, _FakeVar, _FakeWidget


def test_constructor_sets_up_window_and_explanations(monkeypatch) -> None:
    root = _FakeRoot()
    registry: dict[str, list[_FakeWidget]] = {
        "labels": [],
        "frames": [],
        "labelframes": [],
        "buttons": [],
        "scales": [],
    }
    config = SimpleNamespace(system_power_extreme_cap_khz=1_300_000)

    def _frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["frames"].append(widget)
        return widget

    def _labelframe(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labelframes"].append(widget)
        return widget

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["buttons"].append(widget)
        return widget

    def _scale(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["scales"].append(widget)
        return widget

    monkeypatch.setattr(power_mode.tk, "Tk", lambda: root)
    monkeypatch.setattr(power_mode.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(power_mode.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(power_mode.ttk, "Frame", _frame)
    monkeypatch.setattr(power_mode.ttk, "LabelFrame", _labelframe)
    monkeypatch.setattr(power_mode.ttk, "Label", _label)
    monkeypatch.setattr(power_mode.ttk, "Button", _button)
    monkeypatch.setattr(power_mode.ttk, "Scale", _scale)
    monkeypatch.setattr(power_mode, "Config", lambda: config)
    monkeypatch.setattr(power_mode, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    focus_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        power_mode, "schedule_initial_focus", lambda root_arg, target: focus_calls.append((root_arg, target))
    )
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (1_025_000, 1_300_000))
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(
            supported=True,
            mode=SimpleNamespace(value="balanced"),
            reason="ok",
            identifiers={
                "can_apply": "true",
                "helper_present": "true",
                "sysfs_writable": "false",
                "configured_extreme_cap_khz": "1300000",
            },
        ),
    )
    monkeypatch.setattr(power_mode, "compute_centered_window_geometry", lambda *_args, **_kwargs: "760x520+10+20")

    gui = power_mode.PowerModeSettingsGUI()

    texts = [widget.kwargs.get("text") for widget in registry["labels"] if "text" in widget.kwargs]

    assert root.title_calls == ["KeyRGB - Power Mode Settings"]
    assert root.minsize_calls == [(700, 460)]
    assert root.geometry_calls == ["760x520+10+20"]
    assert any(delay == 50 for delay, _callback in root.after_calls)
    assert any(delay == power_mode._LIVE_PREVIEW_INTERVAL_MS for delay, _callback in root.after_calls)
    assert power_mode._INTRO_TEXT in texts
    assert power_mode._EXTREME_HELP_TEXT in texts
    assert power_mode._BALANCED_HELP_TEXT in texts
    assert power_mode._PERFORMANCE_HELP_TEXT in texts
    assert power_mode._CAP_NOTE_TEXT in texts
    assert gui._cap_value_var.get() == "1300 MHz"
    assert gui._live_freq_var.get() == "Live CPU avg/max: 1025 / 1300 MHz"

    footer_label = next(
        widget for widget in registry["labels"] if widget.kwargs.get("textvariable") is gui._save_status_var
    )
    assert footer_label.grid_calls == [{"row": 0, "column": 0, "columnspan": 4, "sticky": "ew", "pady": (0, 6)}]
    live_freq_label = next(
        widget for widget in registry["labels"] if widget.kwargs.get("textvariable") is gui._live_freq_var
    )
    assert live_freq_label.grid_calls == [{"row": 2, "column": 0, "columnspan": 4, "sticky": "w", "pady": (12, 0)}]

    from keyrgb.gui.theme import metrics as theme_metrics

    main_frame = registry["frames"][0]
    assert main_frame.kwargs.get("padding") == theme_metrics.OUTER_PADDING
    title_label = next(widget for widget in registry["labels"] if widget.kwargs.get("text") == "Power Mode Settings")
    assert title_label.kwargs.get("style") == theme_metrics.TITLE_LABEL_STYLE
    assert "font" not in title_label.kwargs
    assert all("font" not in widget.kwargs for widget in registry["labels"])
    cap_value_label = next(
        widget for widget in registry["labels"] if widget.kwargs.get("textvariable") is gui._cap_value_var
    )
    assert cap_value_label.kwargs.get("style") == theme_metrics.VALUE_LABEL_STYLE
    assert footer_label.kwargs.get("style") == theme_metrics.STATUS_LABEL_STYLE
    assert live_freq_label.kwargs.get("style") == theme_metrics.STATUS_LABEL_STYLE
    save_button = next(widget for widget in registry["buttons"] if widget.kwargs.get("text") == "Save")
    assert save_button.kwargs.get("style") == theme_metrics.PRIMARY_BUTTON_STYLE
    assert gui.btn_save is save_button
    assert focus_calls == [(root, save_button)]


def test_shortcuts_route_close_and_save_to_exact_handlers(monkeypatch) -> None:
    root = _FakeRoot()
    registry: dict[str, list[_FakeWidget]] = {
        "labels": [],
        "frames": [],
        "labelframes": [],
        "buttons": [],
        "scales": [],
    }
    config = SimpleNamespace(system_power_extreme_cap_khz=1_300_000)

    def _frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["frames"].append(widget)
        return widget

    def _labelframe(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labelframes"].append(widget)
        return widget

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["buttons"].append(widget)
        return widget

    def _scale(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["scales"].append(widget)
        return widget

    monkeypatch.setattr(power_mode.tk, "Tk", lambda: root)
    monkeypatch.setattr(power_mode.tk, "DoubleVar", _FakeVar)
    monkeypatch.setattr(power_mode.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(power_mode.ttk, "Frame", _frame)
    monkeypatch.setattr(power_mode.ttk, "LabelFrame", _labelframe)
    monkeypatch.setattr(power_mode.ttk, "Label", _label)
    monkeypatch.setattr(power_mode.ttk, "Button", _button)
    monkeypatch.setattr(power_mode.ttk, "Scale", _scale)
    monkeypatch.setattr(power_mode, "Config", lambda: config)
    monkeypatch.setattr(power_mode, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(power_mode, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    focus_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        power_mode, "schedule_initial_focus", lambda root_arg, target: focus_calls.append((root_arg, target))
    )
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (1_025_000, 1_300_000))
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(
            supported=True,
            mode=SimpleNamespace(value="balanced"),
            reason="ok",
            identifiers={},
        ),
    )
    monkeypatch.setattr(power_mode, "compute_centered_window_geometry", lambda *_args, **_kwargs: "760x520+10+20")

    gui = power_mode.PowerModeSettingsGUI()

    # WM protocol is preserved on the exact orderly close path.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._close)]
    # Exact shortcut set with save, all additive, no native navigation.
    assert [sequence for sequence, _, _ in root.bind_calls] == ["<Control-w>", "<Escape>", "<Control-s>"]
    assert all(add == "+" for _, _, add in root.bind_calls)
    assert all("Tab" not in sequence for sequence, _, _ in root.bind_calls)
    assert root.bind_calls[0][1] is root.bind_calls[1][1]
    assert root.bind_calls[0][1] is not root.bind_calls[2][1]
    # The Save shortcut shares the exact handler wired to the Save button.
    save_button = next(widget for widget in registry["buttons"] if widget.kwargs.get("text") == "Save")
    assert save_button.kwargs.get("command") == gui._save
    # Existing close/geometry ordering stays: centered fallback still runs.
    assert root.geometry_calls == ["760x520+10+20"]
    # Save shortcut returns break and invokes the exact Save-button handler.
    submits: list[tuple[object, object]] = []
    monkeypatch.setattr(
        power_mode, "submit_gui_work", lambda owner, root_arg, work, on_done: submits.append((work, on_done))
    )
    assert root.bind_calls[2][1](object()) == "break"
    assert submits != []
    # Close shortcuts return break and invoke the exact _close route once.
    assert root.bind_calls[0][1](object()) == "break"
    assert root.destroy_calls == 1


def test_sync_cap_label_and_refresh_helpers(monkeypatch) -> None:
    gui = SimpleNamespace(
        _cap_value_var=SimpleNamespace(set=MagicMock()),
        _configured_cap_khz=lambda: 800_000,
        _status_var=SimpleNamespace(set=MagicMock()),
        _live_freq_var=SimpleNamespace(set=MagicMock()),
        root=SimpleNamespace(after=MagicMock()),
    )
    # Bound-method style refresh needs the callback attribute present on self.
    gui._refresh_live_freq_preview = lambda: None
    monkeypatch.setattr(power_mode, "_format_cap_mhz_label", lambda khz: f"{khz}")
    monkeypatch.setattr(power_mode, "_format_status_text", lambda: "status")
    monkeypatch.setattr(power_mode, "_format_live_freq_text", lambda: "live")

    power_mode.PowerModeSettingsGUI._sync_cap_label(gui, "900")
    gui._cap_value_var.set.assert_called()
    power_mode.PowerModeSettingsGUI._sync_cap_label(gui, "bad")
    power_mode.PowerModeSettingsGUI._refresh_status(gui)
    gui._status_var.set.assert_called_with("status")

    power_mode.PowerModeSettingsGUI._refresh_live_freq_preview(gui)
    gui._live_freq_var.set.assert_called_with("live")
    gui.root.after.assert_called()

    # geometry errors stop refresh loop
    gui.root.after.side_effect = power_mode.tk.TclError("gone")
    power_mode.PowerModeSettingsGUI._refresh_live_freq_preview(gui)


def test_apply_geometry_swallows_errors(monkeypatch) -> None:
    gui = SimpleNamespace(
        root=SimpleNamespace(update_idletasks=MagicMock(), geometry=MagicMock()),
        _main_frame=SimpleNamespace(winfo_reqheight=lambda: 100, winfo_reqwidth=lambda: 200),
    )
    monkeypatch.setattr(
        power_mode,
        "compute_centered_window_geometry",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("geo")),
    )
    power_mode.PowerModeSettingsGUI._apply_geometry(gui)
