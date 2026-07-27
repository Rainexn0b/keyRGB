from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.gui.windows import power_mode


class _FakeVar:
    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", 620))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 520))


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.update_idletasks_calls = 0
        self.destroy_calls = 0

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

    def destroy(self) -> None:
        self.destroy_calls += 1


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
    assert footer_label.grid_calls == [{"row": 0, "column": 0, "columnspan": 4, "sticky": "ew", "pady": (0, 10)}]
    live_freq_label = next(
        widget for widget in registry["labels"] if widget.kwargs.get("textvariable") is gui._live_freq_var
    )
    assert live_freq_label.grid_calls == [{"row": 2, "column": 0, "columnspan": 4, "sticky": "w", "pady": (12, 0)}]


def test_save_persists_clamped_extreme_cap_and_refreshes_status(monkeypatch) -> None:
    gui = power_mode.PowerModeSettingsGUI.__new__(power_mode.PowerModeSettingsGUI)
    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui.config = config
    gui._cap_var = _FakeVar(123.0)
    gui._cap_value_var = _FakeVar("")
    gui._save_status_var = _FakeVar("")
    gui._status_var = _FakeVar("")
    refreshed: list[str] = []
    gui._refresh_status = lambda: refreshed.append("status")
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=SimpleNamespace(value="balanced"), reason="ok", identifiers={}),
    )

    gui._save()

    assert config.system_power_extreme_cap_khz == 400_000
    assert gui._cap_value_var.get() == "400 MHz"
    assert "Extreme Saver target" in gui._save_status_var.get()
    assert refreshed == ["status"]


def test_save_reapplies_extreme_saver_when_active(monkeypatch) -> None:
    gui = power_mode.PowerModeSettingsGUI.__new__(power_mode.PowerModeSettingsGUI)
    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui.config = config
    gui._cap_var = _FakeVar(1004.0)
    gui._cap_value_var = _FakeVar("")
    gui._save_status_var = _FakeVar("")
    gui._status_var = _FakeVar("")
    refreshed: list[str] = []
    reapplied: list[power_mode.PowerMode] = []
    gui._refresh_status = lambda: refreshed.append("status")
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.EXTREME_SAVER, reason="ok", identifiers={}),
    )
    monkeypatch.setattr(power_mode, "set_mode", lambda mode: reapplied.append(mode) or True)

    gui._save()

    assert config.system_power_extreme_cap_khz == 1_004_000
    assert gui._cap_value_var.get() == "1004 MHz"
    assert gui._save_status_var.get() == "Saved and reapplied Extreme Saver."
    assert reapplied == [power_mode.PowerMode.EXTREME_SAVER]
    assert refreshed == ["status"]


def test_format_status_text_includes_apply_path_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(
            supported=True,
            mode=SimpleNamespace(value="extreme-saver"),
            reason="ok",
            identifiers={
                "can_apply": "false",
                "helper_present": "false",
                "sysfs_writable": "false",
                "configured_extreme_cap_khz": "1004000",
            },
        ),
    )

    text = power_mode._format_status_text()

    assert "Current mode: Extreme Saver" in text
    assert "Can apply: no" in text
    assert "Helper installed: no" in text
    assert "Configured target: 1004 MHz" in text


def test_format_live_freq_text_formats_average_mhz(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (612_500, 1_017_000))

    text = power_mode._format_live_freq_text()

    assert text == "Live CPU avg/max: 612 / 1017 MHz"


def test_format_status_text_error_and_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_status", lambda: (_ for _ in ()).throw(OSError("nope")))
    assert power_mode._format_status_text() == "Status: unavailable"

    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=False, reason="", mode=None, identifiers={}),
    )
    assert "unavailable" in power_mode._format_status_text()

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
                "sysfs_writable": "true",
                "configured_extreme_cap_khz": "not-int",
            },
        ),
    )
    text = power_mode._format_status_text()
    assert "Balanced" in text
    assert "Configured target" not in text


def test_format_live_freq_text_error_paths(monkeypatch) -> None:
    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: unavailable"

    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (None, None))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: unavailable"

    monkeypatch.setattr(power_mode, "get_current_freq_stats_khz", lambda: (500_000, None))
    assert power_mode._format_live_freq_text() == "Live CPU avg/max: 500 MHz / unavailable"


def test_mode_title_and_cap_helpers() -> None:
    assert power_mode._mode_title(None) == "Unknown"
    assert power_mode._mode_title("extreme-saver") == "Extreme Saver"
    assert power_mode._cap_mhz_bounds()[0] < power_mode._cap_mhz_bounds()[1]
    assert "MHz" in power_mode._format_cap_mhz_label(1_000_000)


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


def test_save_not_extreme_and_set_mode_failure(monkeypatch) -> None:
    from unittest.mock import MagicMock

    config = SimpleNamespace(system_power_extreme_cap_khz=800_000)
    gui = SimpleNamespace(
        config=config,
        _selected_cap_khz=lambda: 900_000,
        _cap_value_var=SimpleNamespace(set=MagicMock()),
        _save_status_var=SimpleNamespace(set=MagicMock()),
        _refresh_status=MagicMock(),
    )
    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.BALANCED),
    )
    monkeypatch.setattr(power_mode, "_format_cap_mhz_label", lambda khz: f"{khz}")
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "next time" in gui._save_status_var.set.call_args.args[0]

    monkeypatch.setattr(
        power_mode,
        "get_status",
        lambda: SimpleNamespace(supported=True, mode=power_mode.PowerMode.EXTREME_SAVER),
    )
    monkeypatch.setattr(power_mode, "set_mode", lambda _m: False)
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "Re-select Extreme Saver" in gui._save_status_var.set.call_args.args[0]

    monkeypatch.setattr(power_mode, "set_mode", lambda _m: (_ for _ in ()).throw(OSError("fail")))
    power_mode.PowerModeSettingsGUI._save(gui)
    assert "Re-select Extreme Saver" in gui._save_status_var.set.call_args.args[0]


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
