from __future__ import annotations

import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace

import pytest

import keyrgb.gui.settings.window as settings_window
from keyrgb.gui.theme import metrics as theme_metrics
from tests.gui.settings.window._settings_window_fakes import (
    _FakeBottomBarPanel,
    _FakeGeometryTracker,
    _FakePanel,
    _FakeRoot,
    _FakeScrollArea,
    _FakeVar,
    _FakeWidget,
    _values,
)


def test_init_sets_up_root_and_calls_init_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    values = _values()
    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(
        settings_window, "apply_keyrgb_window_icon", lambda actual_root: calls.append(("icon", (actual_root,), {}))
    )
    monkeypatch.setattr(
        settings_window,
        "apply_clam_theme",
        lambda actual_root, **kwargs: calls.append(("theme", (actual_root,), kwargs)) or ("#111", "#eee"),
    )
    monkeypatch.setattr(settings_window, "Config", lambda: calls.append(("config", (), {})) or "config-obj")
    monkeypatch.setattr(
        settings_window, "detect_os_autostart_enabled", lambda: calls.append(("detect", (), {})) or True
    )
    monkeypatch.setattr(
        settings_window, "load_settings_values", lambda **kwargs: calls.append(("load", (), kwargs)) or values
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_init_layout", lambda self, **kwargs: calls.append(("layout", (), kwargs))
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_init_vars", lambda self, values: calls.append(("vars", (values,), {}))
    )
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: calls.append(("panels", (), {})))
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: calls.append(("finalize", (), {}))
    )
    monkeypatch.setattr(
        settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: calls.append(("probe", (), {}))
    )
    gui = settings_window.PowerSettingsGUI()
    assert gui.root is root
    assert gui.config == "config-obj"
    assert root.title_calls == ["KeyRGB - Settings"]
    assert root.minsize_calls == [(680, 560)]
    assert root.resizable_calls == [(True, True)]
    # The window-manager close button shares the orderly close path so the
    # persisted geometry is saved before destruction.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._on_close)]
    assert calls == [
        ("icon", (root,), {}),
        ("theme", (root,), {}),
        ("config", (), {}),
        ("detect", (), {}),
        ("load", (), {"config": "config-obj", "os_autostart_enabled": True}),
        ("layout", (), {"bg_color": "#111"}),
        ("vars", (values,), {}),
        ("panels", (), {}),
        ("finalize", (), {}),
        ("probe", (), {}),
    ]


def test_start_footer_hardware_probe_runs_worker_and_updates_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = _FakeBottomBarPanel(None, on_close=lambda: None)
    fake_collectors = ModuleType("keyrgb.core.diagnostics.collectors.backends")
    fake_collectors.backend_probe_snapshot = lambda: "snapshot"
    monkeypatch.setitem(sys.modules, "keyrgb.core.diagnostics.collectors.backends", fake_collectors)
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
    fake_collectors = ModuleType("keyrgb.core.diagnostics.collectors.backends")
    fake_collectors.backend_probe_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "keyrgb.core.diagnostics.collectors.backends", fake_collectors)
    monkeypatch.setattr(settings_window, "run_in_thread", lambda root, work, on_done, *, delay_ms: on_done(work()))
    gui._start_footer_hardware_probe()


def test_init_layout_builds_title_notebook_and_per_page_scroll(monkeypatch: pytest.MonkeyPatch) -> None:
    frames: list[_FakeWidget] = []
    labels: list[_FakeWidget] = []
    notebooks: list[_FakeWidget] = []

    class _FakeNotebook(_FakeWidget):
        def __init__(self, parent=None, **kwargs) -> None:
            super().__init__(parent, **kwargs)
            self.add_calls: list[dict[str, object]] = []
            self.select_calls: list[object] = []
            self.bind_calls: list[tuple[str, object]] = []

        def add(self, child, **kwargs) -> None:
            self.add_calls.append({"child": child, **kwargs})

        def select(self, child) -> None:
            self.select_calls.append(child)

        def bind(self, sequence, callback) -> None:
            self.bind_calls.append((sequence, callback))

    def fake_notebook(parent=None, **kwargs):
        notebook = _FakeNotebook(parent, **kwargs)
        notebooks.append(notebook)
        return notebook

    focus_calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        settings_window,
        "schedule_initial_focus",
        lambda root, target: focus_calls.append((root, target)),
    )

    scroll_areas: dict[str, _FakeScrollArea] = {}
    build_calls: list[dict[str, object]] = []

    def fake_build_navigation(parent, **kwargs):
        from types import SimpleNamespace as _NS

        build_calls.append(dict(kwargs))
        pages = {}
        panel_parents = {}
        panel_to_category = {
            "management": "lighting_power",
            "power_source": "lighting_power",
            "dim_sync": "automation",
            "time_scheduler": "automation",
            "autostart": "app",
            "idle_transition_advanced": "advanced",
            "experimental": "advanced",
            "version": "about",
        }
        for category_id in ("lighting_power", "automation", "app", "advanced", "about"):
            page = _FakeWidget(parent)
            pages[category_id] = page
            scroll_areas[category_id] = _FakeScrollArea(page, bg_color=kwargs["bg_color"], padding=kwargs["padding"])
        for panel_id, category_id in panel_to_category.items():
            panel_parents[panel_id] = scroll_areas[category_id].frame
        notebook = fake_notebook(parent)
        return _NS(
            notebook=notebook,
            page_frames=pages,
            scroll_areas=dict(scroll_areas),
            panel_parents=panel_parents,
        )

    monkeypatch.setattr(
        settings_window,
        "ttk",
        SimpleNamespace(
            Frame=lambda parent=None, **kwargs: frames.append(_FakeWidget(parent, **kwargs)) or frames[-1],
            Label=lambda parent=None, **kwargs: labels.append(_FakeWidget(parent, **kwargs)) or labels[-1],
            Notebook=fake_notebook,
        ),
    )
    monkeypatch.setattr(settings_window, "BottomBarPanel", _FakeBottomBarPanel)
    monkeypatch.setattr(settings_window, "build_settings_navigation", fake_build_navigation)
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._on_close = lambda: None
    gui._init_layout(bg_color="#123456")
    assert isinstance(gui.bottom_bar_panel, _FakeBottomBarPanel)
    assert gui.bottom_bar is gui.bottom_bar_panel.frame
    assert gui.status is gui.bottom_bar_panel.status
    # Global title stays outside the tabs; one scroll area per category page.
    assert labels[0].kwargs["text"] == "Settings"
    assert labels[0].kwargs["style"] == theme_metrics.TITLE_LABEL_STYLE
    assert "font" not in labels[0].kwargs
    assert set(gui.scroll_areas) == {"lighting_power", "automation", "app", "advanced", "about"}
    for area in gui.scroll_areas.values():
        assert area.bg_color == "#123456"
        assert area.padding == theme_metrics.OUTER_PAD_X
    assert len(notebooks) == 1
    assert notebooks[0].pack_calls == [
        {"fill": "both", "expand": True, "padx": theme_metrics.CONTROL_GAP_Y, "pady": (2, theme_metrics.CONTROL_GAP_Y)}
    ]
    # Intentional non-forcing initial focus lands on the notebook exactly once.
    assert focus_calls == [(gui.root, gui.notebook)]
    # Panel placement comes from the navigation mapping, built exactly once.
    assert len(build_calls) == 1
    assert gui.panel_parents == {
        panel_id: scroll_areas[category_id].frame
        for panel_id, category_id in {
            "management": "lighting_power",
            "power_source": "lighting_power",
            "dim_sync": "automation",
            "time_scheduler": "automation",
            "autostart": "app",
            "idle_transition_advanced": "advanced",
            "experimental": "advanced",
            "version": "about",
        }.items()
    }
    # No tab-change hook: switching tabs reselects only, never rebuilds.
    assert notebooks[0].bind_calls == []
    notebooks[0].select(gui.page_frames["automation"])
    notebooks[0].select(gui.page_frames["about"])
    assert notebooks[0].select_calls[-2:] == [gui.page_frames["automation"], gui.page_frames["about"]]
    assert len(build_calls) == 1


def test_init_vars_creates_all_expected_tk_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    bool_vars: list[_FakeVar] = []
    double_vars: list[_FakeVar] = []
    string_vars: list[_FakeVar] = []
    int_vars: list[_FakeVar] = []
    monkeypatch.setattr(
        settings_window,
        "tk",
        SimpleNamespace(
            BooleanVar=lambda value=False: bool_vars.append(_FakeVar(value)) or bool_vars[-1],
            DoubleVar=lambda value=0.0: double_vars.append(_FakeVar(value)) or double_vars[-1],
            StringVar=lambda value="": string_vars.append(_FakeVar(value)) or string_vars[-1],
            IntVar=lambda value=0: int_vars.append(_FakeVar(value)) or int_vars[-1],
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
    assert gui.var_ac_power_mode.get() == "Balanced"
    assert gui.var_battery_power_mode.get() == "Keep current power mode"
    assert gui.var_dim_sync_enabled.get() is True
    assert gui.var_dim_sync_mode.get() == "temp"
    assert gui.var_dim_temp_brightness.get() == 7.0
    # UI exposes delays in seconds (0.5s steps); config stores polls.
    assert gui.var_debounce_enter.get() == 3.0
    assert gui.var_debounce_exit.get() == 5.0
    assert gui.var_idle_fade_duration.get() == 0.6
    assert gui.var_scheduler_enabled.get() is False
    assert gui.var_day_start.get() == "08:00"
    assert gui.var_night_start.get() == "20:00"
    assert gui.var_day_base.get() == 40.0
    assert gui.var_day_reactive.get() == 50.0
    assert gui.var_night_base.get() == 20.0
    assert gui.var_night_reactive.get() == 50.0
    assert len(bool_vars) == 13
    assert len(double_vars) == 10
    assert len(string_vars) == 5
    assert len(int_vars) == 0


def test_init_panels_builds_panel_stack_with_expected_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    separators: list[_FakeWidget] = []
    monkeypatch.setattr(
        settings_window,
        "ttk",
        SimpleNamespace(
            Separator=lambda parent=None, **kwargs: separators.append(_FakeWidget(parent, **kwargs)) or separators[-1]
        ),
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
    monkeypatch.setattr(settings_window, "_detect_idle_power_source", lambda: "Wayland compositor idle")
    monkeypatch.setattr(settings_window, "PowerSourcePanel", make_panel("power_source"))
    monkeypatch.setattr(settings_window, "TimeSchedulerPanel", make_panel("time_scheduler"))
    monkeypatch.setattr(settings_window, "VersionPanel", make_panel("version"))
    monkeypatch.setattr(settings_window, "AutostartPanel", make_panel("autostart"))
    monkeypatch.setattr(settings_window, "IdleTransitionAdvancedPanel", make_panel("idle_transition_advanced"))
    monkeypatch.setattr(settings_window, "ExperimentalBackendsPanel", make_panel("experimental"))
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    lighting = _FakeWidget()
    automation = _FakeWidget()
    app_page = _FakeWidget()
    advanced = _FakeWidget()
    about = _FakeWidget()
    gui.panel_parents = {
        "management": lighting,
        "power_source": lighting,
        "dim_sync": automation,
        "time_scheduler": automation,
        "autostart": app_page,
        "idle_transition_advanced": advanced,
        "experimental": advanced,
        "version": about,
    }
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
    gui.var_ac_power_mode = _FakeVar("Balanced")
    gui.var_battery_power_mode = _FakeVar("Keep current power mode")
    gui.var_dim_sync_enabled = _FakeVar(True)
    gui.var_controller_sleep_respect = _FakeVar(False)
    gui.var_dim_sync_mode = _FakeVar("off")
    gui.var_dim_temp_brightness = _FakeVar(5.0)
    gui.var_debounce_enter = _FakeVar(6)
    gui.var_debounce_exit = _FakeVar(10)
    gui.var_idle_fade_duration = _FakeVar(0.6)
    gui.var_scheduler_enabled = _FakeVar(False)
    gui.var_day_start = _FakeVar("08:00")
    gui.var_night_start = _FakeVar("20:00")
    gui.var_day_base = _FakeVar(40.0)
    gui.var_day_reactive = _FakeVar(50.0)
    gui.var_night_base = _FakeVar(20.0)
    gui.var_night_reactive = _FakeVar(50.0)
    gui.var_autostart = _FakeVar(True)
    gui.var_os_autostart = _FakeVar(False)
    gui.var_experimental_backends = _FakeVar(False)
    gui._on_toggle = lambda: None
    gui._init_panels()
    assert created["management"].args == (lighting,)
    assert created["power_source"].args == (lighting,)
    assert created["power_source"].kwargs["var_ac_brightness"] is gui.var_ac_brightness
    assert created["power_source"].kwargs["var_ac_power_mode"] is gui.var_ac_power_mode
    assert created["power_source"].kwargs["var_battery_power_mode"] is gui.var_battery_power_mode
    assert created["power_source"].kwargs["power_mode_options"] == (
        "Keep current power mode",
        "Extreme Saver",
        "Balanced",
        "Performance",
    )
    assert created["time_scheduler"].args == (automation,)
    assert created["time_scheduler"].kwargs["var_enabled"] is gui.var_scheduler_enabled
    assert created["dim_sync"].args == (automation,)
    assert created["dim_sync"].kwargs["idle_source_label"] == "Wayland compositor idle"
    assert created["dim_sync"].kwargs["var_dim_sync_enabled"] is gui.var_dim_sync_enabled
    assert created["dim_sync"].kwargs["var_dim_sync_mode"] is gui.var_dim_sync_mode
    assert created["dim_sync"].kwargs["var_dim_temp_brightness"] is gui.var_dim_temp_brightness
    assert created["autostart"].args == (app_page,)
    assert created["idle_transition_advanced"].args == (advanced,)
    assert created["idle_transition_advanced"].kwargs["var_controller_sleep_respect"] is (
        gui.var_controller_sleep_respect
    )
    assert created["idle_transition_advanced"].kwargs["var_debounce_enter"] is gui.var_debounce_enter
    assert created["idle_transition_advanced"].kwargs["var_debounce_exit"] is gui.var_debounce_exit
    assert created["idle_transition_advanced"].kwargs["var_idle_fade_duration"] is gui.var_idle_fade_duration
    assert created["experimental"].args == (advanced,)
    assert created["version"].args == (about,)
    assert created["version"].kwargs["root"] is gui.root
    assert created["version"].kwargs["get_status_label"]() is gui.status
    # One separator between the two panels sharing Lighting & Power, one
    # in Automation, and one in Advanced; single-panel pages need no separator.
    assert len(separators) == 3
    assert separators[0].parent is lighting
    assert separators[1].parent is automation
    assert separators[2].parent is advanced


def test_init_vars_uses_canonical_night_start_fallback_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    string_vars: list[_FakeVar] = []
    bool_vars: list[_FakeVar] = []
    double_vars: list[_FakeVar] = []
    int_vars: list[_FakeVar] = []
    monkeypatch.setattr(
        settings_window.tk, "StringVar", lambda value=None: string_vars.append(_FakeVar(value)) or string_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "BooleanVar", lambda value=None: bool_vars.append(_FakeVar(value)) or bool_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "DoubleVar", lambda value=None: double_vars.append(_FakeVar(value)) or double_vars[-1]
    )
    monkeypatch.setattr(
        settings_window.tk, "IntVar", lambda value=None: int_vars.append(_FakeVar(value)) or int_vars[-1]
    )

    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    values = replace(_values(), night_start_time="")
    gui._init_vars(values)
    assert gui.var_night_start.get() == "20:00"


def test_finalize_layout_applies_state_scroll_and_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._geometry_tracker = _FakeGeometryTracker(gui.root, "settings", 680, 560, 0.95)
    area_lighting = _FakeScrollArea(None, bg_color="#000", padding=10)
    area_automation = _FakeScrollArea(None, bg_color="#000", padding=10)
    gui.scroll_areas = {"lighting_power": area_lighting, "automation": area_automation}
    gui.bottom_bar = _FakeWidget()
    calls: list[str] = []
    gui._apply_enabled_state = lambda: calls.append("enabled")
    gui._apply_geometry = lambda: calls.append("geometry")
    gui._finalize_layout()
    assert calls == ["enabled"]
    assert gui.root.geometry_calls == ["880x840"]
    for area in (area_lighting, area_automation):
        assert area.bind_mousewheel_calls == [(gui.root, None)]
        assert area.canvas.configure_calls == [{"scrollregion": (1, 2, 3, 4)}]
        assert area.canvas.bbox_calls == ["all"]
        assert area.finalize_calls == 1
    assert gui.root.update_calls == 1
    assert gui._geometry_tracker.restore_calls == 1
    assert gui._geometry_tracker.start_tracking_calls == 0
    assert gui.root.after_calls == [
        (50, gui._apply_geometry),
        (350, gui._apply_geometry),
        (400, gui._geometry_tracker.start_tracking),
    ]


def test_finalize_layout_swallows_scrollregion_errors() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui._geometry_tracker = _FakeGeometryTracker(gui.root, "settings", 680, 560, 0.95)
    failing = _FakeScrollArea(None, bg_color="#000", padding=10)
    failing.canvas.configure = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    passing = _FakeScrollArea(None, bg_color="#000", padding=10)
    gui.scroll_areas = {"lighting_power": failing, "automation": passing}
    gui.bottom_bar = _FakeWidget()
    gui._apply_enabled_state = lambda: None
    gui._apply_geometry = lambda: None
    gui._finalize_layout()
    assert passing.canvas.configure_calls == [{"scrollregion": (1, 2, 3, 4)}]
    assert passing.finalize_calls == 1
    assert failing.finalize_calls == 1
    assert gui.root.after_calls == [
        (50, gui._apply_geometry),
        (350, gui._apply_geometry),
        (400, gui._geometry_tracker.start_tracking),
    ]


def test_apply_geometry_sizes_from_default_page_only(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    default_page = SimpleNamespace(frame=_FakeWidget())
    default_page.frame.reqheight = 400
    default_page.frame.reqwidth = 600
    hidden_tall_page = SimpleNamespace(frame=_FakeWidget())
    hidden_tall_page.frame.reqheight = 1400
    hidden_tall_page.frame.reqwidth = 1200
    gui.scroll_areas = {"lighting_power": default_page, "automation": hidden_tall_page}
    gui.bottom_bar = _FakeWidget()
    gui.bottom_bar.reqheight = 44
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        settings_window,
        "compute_centered_window_geometry",
        lambda *args, **kwargs: calls.append(kwargs) or "1100x850+10+20",
    )
    gui._apply_geometry()
    assert gui.root.update_calls == 1
    assert gui.root.geometry_calls == ["1100x850+10+20"]
    # The taller hidden page scrolls independently and must not inflate the
    # window; the stable default keeps the 880x840 budget.
    assert calls == [
        {
            "content_height_px": 400,
            "content_width_px": 600,
            "footer_height_px": 44,
            "chrome_padding_px": 40,
            "default_w": 880,
            "default_h": 840,
            "screen_ratio_cap": 0.95,
        }
    ]


def test_apply_enabled_state_delegates_to_panels() -> None:
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.var_enabled = _FakeVar(False)
    gui.management_panel = _FakePanel()
    gui.dim_sync_panel = _FakePanel()
    gui.idle_transition_advanced_panel = _FakePanel()
    gui.power_source_panel = _FakePanel()
    gui.time_scheduler_panel = _FakePanel()
    gui._apply_enabled_state()
    assert gui.management_panel.apply_calls == [{}]
    assert gui.dim_sync_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.idle_transition_advanced_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.power_source_panel.apply_calls == [{"power_management_enabled": False}]
    assert gui.time_scheduler_panel.apply_calls == [{}]


def test_tab_switch_has_no_rebuild_path_and_probes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin one-time construction without invoking an unrelated fake select.

    The real ``__init__`` call order (layout/vars/panels/finalize/probe each
    exactly once) is pinned by ``test_init_sets_up_root_and_calls_init_steps``,
    one-time page construction by the navigation tests, and the absence of a
    tab-change rebuild hook by the layout test's ``bind_calls == []``
    assertion. This test pins the remaining half: the footer probe is issued
    exactly once per window.
    """
    gui = settings_window.PowerSettingsGUI.__new__(settings_window.PowerSettingsGUI)
    gui.root = _FakeRoot()
    gui.bottom_bar_panel = _FakeBottomBarPanel(None, on_close=lambda: None)
    probe_runs: list[int] = []
    monkeypatch.setattr(settings_window, "run_in_thread", lambda *args, **kwargs: probe_runs.append(1) or None)
    gui._start_footer_hardware_probe()
    assert len(probe_runs) == 1


def test_shortcuts_route_to_orderly_close_without_save(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot()
    values = _values()
    monkeypatch.setattr(settings_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings_window, "apply_keyrgb_window_icon", lambda _root: None)
    monkeypatch.setattr(settings_window, "apply_clam_theme", lambda _root, **_kwargs: ("#111", "#eee"))
    monkeypatch.setattr(settings_window, "Config", lambda: SimpleNamespace(physical_layout="auto"))
    monkeypatch.setattr(settings_window, "detect_os_autostart_enabled", lambda: False)
    monkeypatch.setattr(settings_window, "load_settings_values", lambda **_kwargs: values)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_layout", lambda self, **_kwargs: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_vars", lambda self, _values: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_init_panels", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_finalize_layout", lambda self: None)
    monkeypatch.setattr(settings_window.PowerSettingsGUI, "_start_footer_hardware_probe", lambda self: None)
    monkeypatch.setattr(settings_window, "WindowGeometryTracker", _FakeGeometryTracker)

    gui = settings_window.PowerSettingsGUI()

    # WM protocol is preserved on the exact orderly close path.
    assert root.protocol_calls == [("WM_DELETE_WINDOW", gui._on_close)]
    # Exact shortcut set: close-only, additive, no save, no native navigation.
    assert [sequence for sequence, _, _ in root.bind_calls] == ["<Control-w>", "<Escape>"]
    assert all(add == "+" for _, _, add in root.bind_calls)
    assert all("Tab" not in sequence for sequence, _, _ in root.bind_calls)
    assert "<Control-s>" not in [sequence for sequence, _, _ in root.bind_calls]
    # Both shortcuts share the same close wrapper.
    assert root.bind_calls[0][1] is root.bind_calls[1][1]
    # The wrapper returns break and invokes the orderly close exactly once.
    assert root.bind_calls[0][1](object()) == "break"
    assert gui.root.destroy_calls == 1
