from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

import src.gui.settings.window as settings_window
from src.gui.settings.settings_state import SettingsValues


class _FakeVar:
    def __init__(self, value=None) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.set_calls.append(value)
        self.value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.bbox_calls: list[object] = []
        self.reqheight = 320
        self.reqwidth = 640

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def bbox(self, tag: object):
        self.bbox_calls.append(tag)
        return (1, 2, 3, 4)

    def winfo_reqheight(self) -> int:
        return self.reqheight

    def winfo_reqwidth(self) -> int:
        return self.reqwidth


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.geometry_calls: list[str] = []
        self.update_calls = 0
        self.mainloop_calls = 0
        self.destroy_calls = 0

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def update_idletasks(self) -> None:
        self.update_calls += 1

    def mainloop(self) -> None:
        self.mainloop_calls += 1

    def destroy(self) -> None:
        self.destroy_calls += 1


class _FakeBottomBarPanel:
    def __init__(self, parent, *, on_close) -> None:
        self.parent = parent
        self.on_close = on_close
        self.frame = _FakeWidget(parent)
        self.status = _FakeWidget(parent)
        self.hint_calls: list[str] = []

    def set_hardware_hint(self, text: str) -> None:
        self.hint_calls.append(text)


class _FakeScrollArea:
    def __init__(self, parent, *, bg_color: str, padding: int) -> None:
        self.parent = parent
        self.bg_color = bg_color
        self.padding = padding
        self.frame = _FakeWidget(parent)
        self.canvas = _FakeWidget(parent)
        self.bind_mousewheel_calls: list[tuple[object, object]] = []
        self.finalize_calls = 0

    def bind_mousewheel(self, root, *, priority_scroll_widget=None) -> None:
        self.bind_mousewheel_calls.append((root, priority_scroll_widget))

    def finalize_initial_scrollbar_state(self) -> None:
        self.finalize_calls += 1


class _FakePanel:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.apply_calls: list[dict[str, object]] = []
        self.frame = _FakeWidget()
        self.txt_diagnostics = _FakeWidget()

    def apply_enabled_state(self, **kwargs) -> None:
        self.apply_calls.append(dict(kwargs))

    def apply_state(self) -> None:
        self.apply_calls.append({"apply_state": True})


def _values() -> SettingsValues:
    return SettingsValues(
        power_management_enabled=True,
        power_off_on_suspend=False,
        power_off_on_lid_close=True,
        power_restore_on_resume=False,
        power_restore_on_lid_open=True,
        autostart=True,
        experimental_backends_enabled=False,
        ac_lighting_enabled=True,
        battery_lighting_enabled=False,
        ac_lighting_brightness=21,
        battery_lighting_brightness=9,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=7,
        os_autostart_enabled=False,
        physical_layout="auto",
    )


def test_init_sets_up_root_and_calls_init_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings_window, "apply_keyrgb_window_icon", lambda actual_root: calls.append(("icon", (actual_root,), {})))
    monkeypatch.setattr(settings_window, "apply_clam_theme", lambda actual_root, **kwargs: calls.append(("theme", (actual_root,), kwargs)) or ("#111", "#eee"))
    monkeypatch.setattr(settings_window, "Config", lambda: calls.append(("config", (), {})) or "config-obj")
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: calls.append(("detect", (), {})) or True)
    monkeypatch.setattr(settings_window, "load_settings_values", lambda **kwargs: calls.append(("load", (), kwargs)) or "values")
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_layout", lambda self, **kwargs: calls.append(("layout", (), kwargs)))
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_vars", lambda self, values: calls.append(("vars", (values,), {})))
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: calls.append(("panels", (), {})))
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: calls.append(("finalize", (), {})))
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: calls.append(("probe", (), {})))

    gui = settings_window.PowerSettingsGUI()

    assert gui.root is root
    assert gui.config == "config-obj"
    assert root.title_calls == ["KeyRGB - Settings"]
    assert root.minsize_calls == [(760, 560)]
    assert root.resizable_calls == [(True, True)]
    assert calls == [
        ("icon", (root,), {}),
        ("theme", (root,), {"include_checkbuttons": True, "map_checkbutton_state": True}),
        ("config", (), {}),
        ("detect", (), {}),
        ("load", (), {"config": "config-obj", "os_autostart_enabled": True}),
        ("layout", (), {"bg_color": "#111"}),
        ("vars", ("values",), {}),
        ("panels", (), {}),
        ("finalize", (), {}),
        ("probe", (), {}),
    ]


def test_start_footer_hardware_probe_runs_worker_and_updates_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = _FakeBottomBarPanel(None, on_close=lambda: None)

    fake_collectors = ModuleType("src.core.diagnostics.collectors_backends")
    fake_collectors.backend_probe_snapshot = lambda: "snapshot"
    monkeypatch.setitem(sys.modules, "src.core.diagnostics.collectors_backends", fake_collectors)
    monkeypatch.setattr(settings_window, "extract_unsupported_rgb_controllers_hint", lambda snap: f"hint:{snap}")

    run_calls: list[tuple[object, object, object, int]] = []

    def fake_run_in_thread(root, work, on_done, *, delay_ms: int) -> None:
        run_calls.append((root, work, on_done, delay_ms))
        on_done(work())

    monkeypatch.setattr(settings_window, "run_in_thread", fake_run_in_thread)

    gui._start_footer_hardware_probe()

    assert run_calls[0][0] is gui.root
    assert run_calls[0][3] == 100
    assert gui.bottom_bar_panel.hint_calls == ["hint:snapshot"]


def test_start_footer_hardware_probe_swallows_worker_and_footer_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = SimpleNamespace(set_hardware_hint=lambda text: (_ for _ in ()).throw(RuntimeError(text)))

    fake_collectors = ModuleType("src.core.diagnostics.collectors_backends")
    fake_collectors.backend_probe_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "src.core.diagnostics.collectors_backends", fake_collectors)
    monkeypatch.setattr(settings_window, "run_in_thread", lambda root, work, on_done, *, delay_ms: on_done(work()))

    gui._start_footer_hardware_probe()


def test_init_layout_builds_frames_bottom_bar_and_scroll(monkeypatch: pytest.MonkeyPatch) -> None:
    frames: list[_FakeWidget] = []
    labels: list[_FakeWidget] = []

    monkeypatch.setattr(
        settings_window,
        "ttk",
        SimpleNamespace(
            Frame=lambda parent=None, **kwargs: frames.append(_FakeWidget(parent, **kwargs)) or frames[-1],
            Label=lambda parent=None, **kwargs: labels.append(_FakeWidget(parent, **kwargs)) or labels[-1],
        ),
    )
    monkeypatch.setattr(settings_window, "BottomBarPanel", _FakeBottomBarPanel)
    monkeypatch.setattr(settings_window, "ScrollableArea", _FakeScrollArea)

    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._on_close = lambda: None

    gui._init_layout(bg_color="#123456")

    assert isinstance(gui.bottom_bar_panel, _FakeBottomBarPanel)
    assert gui.bottom_bar is gui.bottom_bar_panel.frame
    assert gui.status is gui.bottom_bar_panel.status
    assert isinstance(gui.scroll, _FakeScrollArea)
    assert gui.scroll.bg_color == "#123456"
    assert labels[0].kwargs["text"] == "Settings"
    assert gui._left.parent is frames[2]
    assert gui._right.parent is frames[2]


def test_init_vars_creates_all_expected_tk_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    bool_vars: list[_FakeVar] = []
    double_vars: list[_FakeVar] = []
    string_vars: list[_FakeVar] = []

    monkeypatch.setattr(
        settings_window,
        "tk",
        SimpleNamespace(
            BooleanVar=lambda value=False: bool_vars.append(_FakeVar(value)) or bool_vars[-1],
            DoubleVar=lambda value=0.0: double_vars.append(_FakeVar(value)) or double_vars[-1],
            StringVar=lambda value="": string_vars.append(_FakeVar(value)) or string_vars[-1],
        ),
    )

    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    values = _values()

    gui._init_vars(values)

    assert gui.var_enabled.get() is True
    assert gui.var_off_suspend.get() is False
    assert gui.var_off_lid.get() is True
    assert gui.var_restore_resume.get() is False
    assert gui.var_restore_lid.get() is True
    assert gui.var_autostart.get() is True
    assert gui.var_experimental_backends.get() is False
    assert gui.var_os_autostart.get() is False
    assert gui.var_ac_enabled.get() is True
    assert gui.var_battery_enabled.get() is False
    assert gui.var_ac_brightness.get() == 21.0
    assert gui.var_battery_brightness.get() == 9.0
    assert gui.var_dim_sync_enabled.get() is True
    assert gui.var_dim_sync_mode.get() == "temp"
    assert gui.var_dim_temp_brightness.get() == 7.0
    assert len(bool_vars) == 11
    assert len(double_vars) == 3
    assert len(string_vars) == 1


def test_init_panels_builds_panel_stack_with_expected_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    separators: list[_FakeWidget] = []
    monkeypatch.setattr(
        settings_window,
        "ttk",
        SimpleNamespace(Separator=lambda parent=None, **kwargs: separators.append(_FakeWidget(parent, **kwargs)) or separators[-1]),
    )

    created: dict[str, _FakePanel] = {}

    def make_panel(name: str):
        def factory(*args, **kwargs):
            panel = _FakePanel(*args, **kwargs)
            created[name] = panel
            return panel

        return factory

    monkeypatch.setattr(settings_window, "PowerManagementPanel", make_panel("management"))
    monkeypatch.setattr(settings_window, "DimSyncPanel", make_panel("dim_sync"))
    monkeypatch.setattr(settings_window, "PowerSourcePanel", make_panel("power_source"))
    monkeypatch.setattr(settings_window, "VersionPanel", make_panel("version"))
    monkeypatch.setattr(settings_window, "AutostartPanel", make_panel("autostart"))
    monkeypatch.setattr(settings_window, "ExperimentalBackendsPanel", make_panel("experimental"))
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._left = object()
    gui._right = object()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(False)
    gui.var_restore_resume = _FakeVar(True)
    gui.var_off_lid = _FakeVar(False)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(True)
    gui.var_ac_brightness = _FakeVar(12.0)
    gui.var_battery_brightness = _FakeVar(5.0)
    gui.var_dim_sync_enabled = _FakeVar(True)
    gui.var_dim_sync_mode = _FakeVar("off")
    gui.var_dim_temp_brightness = _FakeVar(5.0)
    gui.var_autostart = _FakeVar(True)
    gui.var_os_autostart = _FakeVar(False)
    gui.var_experimental_backends = _FakeVar(False)
    gui._on_toggle = lambda: None

    gui._init_panels()

    assert created["management"].args == (gui._left,)
    assert created["power_source"].kwargs["var_ac_brightness"] is gui.var_ac_brightness
    assert created["version"].kwargs["root"] is gui.root
    assert created["version"].kwargs["get_status_label"]() is gui.status
    assert len(separators) == 5


def test_finalize_layout_applies_state_scroll_and_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.scroll = _FakeScrollArea(None, bg_color="#000", padding=16)
    gui.bottom_bar = _FakeWidget()
    calls: list[str] = []
    gui._apply_enabled_state = lambda: calls.append("enabled")
    gui._apply_geometry = lambda: calls.append("geometry")

    gui._finalize_layout()

    assert calls == ["enabled"]
    assert gui.scroll.bind_mousewheel_calls == [(gui.root, None)]
    assert gui.scroll.canvas.configure_calls == [{"scrollregion": (1, 2, 3, 4)}]
    assert gui.scroll.canvas.bbox_calls == ["all"]
    assert gui.scroll.finalize_calls == 1
    assert gui.root.update_calls == 1
    assert gui.root.after_calls == [(50, gui._apply_geometry)]


def test_finalize_layout_swallows_scrollregion_errors() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.scroll = _FakeScrollArea(None, bg_color="#000", padding=16)
    gui.scroll.canvas.configure = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    gui.bottom_bar = _FakeWidget()
    gui._apply_enabled_state = lambda: None
    gui._apply_geometry = lambda: None

    gui._finalize_layout()

    assert gui.root.after_calls == [(50, gui._apply_geometry)]


def test_apply_geometry_uses_centered_geometry_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.scroll = SimpleNamespace(frame=_FakeWidget())
    gui.scroll.frame.reqheight = 700
    gui.scroll.frame.reqwidth = 900
    gui.bottom_bar = _FakeWidget()
    gui.bottom_bar.reqheight = 44
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(settings_window, "compute_centered_window_geometry", lambda *args, **kwargs: calls.append(kwargs) or "1100x850+10+20")

    gui._apply_geometry()

    assert gui.root.update_calls == 1
    assert gui.root.geometry_calls == ["1100x850+10+20"]
    assert calls == [
        {
            "content_height_px": 700,
            "content_width_px": 900,
            "footer_height_px": 44,
            "chrome_padding_px": 40,
            "default_w": 1100,
            "default_h": 850,
            "screen_ratio_cap": 0.95,
        }
    ]


def test_apply_enabled_state_delegates_to_panels() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.var_enabled = _FakeVar(False)
    gui.management_panel = _FakePanel()
    gui.dim_sync_panel = _FakePanel()
    gui.power_source_panel = _FakePanel()

    gui._apply_enabled_state()

    assert gui.management_panel.apply_calls == [{}]
    assert gui.dim_sync_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.power_source_panel.apply_calls == [{"power_management_enabled": False}]


def test_on_toggle_saves_values_updates_state_and_schedules_status_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="ansi")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(False)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(False)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(False)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(False)
    gui.var_ac_brightness = _FakeVar(12.9)
    gui.var_battery_brightness = _FakeVar(8.2)
    gui.var_dim_sync_enabled = _FakeVar(True)
    gui.var_dim_sync_mode = _FakeVar("temp")
    gui.var_dim_temp_brightness = _FakeVar(4.4)
    gui.var_os_autostart = _FakeVar(True)
    apply_calls: list[SettingsValues] = []
    monkeypatch.setattr(settings_window, "apply_settings_values_to_config", lambda *, config, values: apply_calls.append(values))
    monkeypatch.setattr(settings_window, "set_os_autostart", lambda enabled: None)
    enabled_calls: list[str] = []
    gui._apply_enabled_state = lambda: enabled_calls.append("enabled")

    gui._on_toggle()

    assert apply_calls and apply_calls[0].ac_lighting_brightness == 12
    assert apply_calls[0].battery_lighting_brightness == 8
    assert apply_calls[0].physical_layout == "ansi"
    assert gui.config.os_autostart is True
    assert enabled_calls == ["enabled"]
    assert gui.status.configure_calls[0] == {"text": "✓ Saved"}
    assert gui.root.after_calls[0][0] == 1500
    gui.root.after_calls[0][1]()
    assert gui.status.configure_calls[-1] == {"text": ""}


def test_on_toggle_recovers_os_autostart_var_when_set_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.config = SimpleNamespace(physical_layout="auto")
    gui.root = _FakeRoot()
    gui.status = _FakeWidget()
    gui.var_enabled = _FakeVar(True)
    gui.var_off_suspend = _FakeVar(True)
    gui.var_off_lid = _FakeVar(True)
    gui.var_restore_resume = _FakeVar(True)
    gui.var_restore_lid = _FakeVar(True)
    gui.var_autostart = _FakeVar(True)
    gui.var_experimental_backends = _FakeVar(False)
    gui.var_ac_enabled = _FakeVar(True)
    gui.var_battery_enabled = _FakeVar(True)
    gui.var_ac_brightness = _FakeVar(10.0)
    gui.var_battery_brightness = _FakeVar(9.0)
    gui.var_dim_sync_enabled = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("off")
    gui.var_dim_temp_brightness = _FakeVar(5.0)
    gui.var_os_autostart = _FakeVar(True)
    monkeypatch.setattr(settings_window, "apply_settings_values_to_config", lambda *, config, values: None)
    monkeypatch.setattr(settings_window, "set_os_autostart", lambda enabled: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: False)
    gui._apply_enabled_state = lambda: None

    gui._on_toggle()

    assert gui.var_os_autostart.set_calls == [False]
    assert gui.status.configure_calls[0] == {"text": "✓ Saved"}


def test_on_close_and_run_delegate_to_root() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()

    gui._on_close()
    gui.run()

    assert gui.root.destroy_calls == 1
    assert gui.root.mainloop_calls == 1