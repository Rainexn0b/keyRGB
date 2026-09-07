from types import SimpleNamespace

import pytest

import keyrgb.tray.app.application as app


def test_init_wires_dependencies_and_starts_pollers(monkeypatch):
    startup_order: list[str] = []
    calls = {
        "deps": 0,
        "select_backend": 0,
        "device_discovery": 0,
        "dimensions": 0,
        "start_power": 0,
        "start_polling": 0,
        "autostart": 0,
    }

    class FakeConfig:
        def __init__(self):
            self.effect = "perkey"
            self.speed = 4
            self.brightness = 50
            self.lightbar_brightness = 25
            self.tray_device_context = "lightbar:048d:7001"

    class FakeEngine:
        def __init__(self, *, backend=None):
            self.backend = backend
            self.stopped = False

        def stop(self):
            self.stopped = True

    class FakePowerManager:
        pass

    fake_pm = SimpleNamespace(stop_monitoring=lambda: None)

    def _load_tray_dependencies():
        calls["deps"] += 1
        return FakeEngine, FakeConfig, FakePowerManager

    def _select_backend_with_introspection():
        calls["select_backend"] += 1
        return "backend", "probe", {"caps": True}

    def _load_ite_dimensions():
        calls["dimensions"] += 1
        return 6, 21

    def _select_device_discovery_snapshot():
        calls["device_discovery"] += 1
        return {"candidates": [{"device_type": "lightbar"}]}

    def _start_power_monitoring(self, *, power_manager_cls, config):
        calls["start_power"] += 1
        assert power_manager_cls is FakePowerManager
        assert isinstance(config, FakeConfig)
        assert self.config is config
        return fake_pm

    def _start_all_polling(self, *, ite_num_rows, ite_num_cols):
        startup_order.append("polling")
        calls["start_polling"] += 1
        assert ite_num_rows == 6
        assert ite_num_cols == 21

    def _maybe_autostart_effect(self):
        startup_order.append("autostart")
        calls["autostart"] += 1

    monkeypatch.setattr(app, "load_tray_dependencies", _load_tray_dependencies)
    monkeypatch.setattr(app, "select_backend_with_introspection", _select_backend_with_introspection)
    monkeypatch.setattr(app, "select_device_discovery_snapshot", _select_device_discovery_snapshot)
    monkeypatch.setattr(app, "load_ite_dimensions", _load_ite_dimensions)
    monkeypatch.setattr(app, "start_power_monitoring", _start_power_monitoring)
    monkeypatch.setattr(app, "start_all_polling", _start_all_polling)
    monkeypatch.setattr(app, "maybe_autostart_effect", _maybe_autostart_effect)

    tray = app.KeyRGBTray()

    assert calls == {
        "deps": 1,
        "select_backend": 1,
        "device_discovery": 1,
        "dimensions": 1,
        "start_power": 1,
        "start_polling": 1,
        "autostart": 1,
    }
    assert startup_order == ["autostart", "polling"]

    assert isinstance(tray.config, FakeConfig)
    assert isinstance(tray.engine, FakeEngine)
    assert tray.engine.backend == "backend"
    assert tray.power_manager is fake_pm
    assert tray.backend == "backend"
    assert tray.backend_probe == "probe"
    assert tray.backend_caps == {"caps": True}
    assert tray.device_discovery == {"candidates": [{"device_type": "lightbar"}]}
    assert hasattr(tray, "system_power_status")
    assert hasattr(tray, "effective_secondary_routes")
    assert tray.selected_device_context == "lightbar:048d:7001"
    assert tray.tray_idle_power_state.idle_forced_off is False
    assert tray.tray_idle_power_state.user_forced_off is False
    assert tray.tray_idle_power_state.power_forced_off is False
    from keyrgb.tray.protocols import TrayIconState

    assert isinstance(tray.tray_icon_state, TrayIconState)
    assert tray._idle_forced_off is False
    assert tray._user_forced_off is False
    assert tray._power_forced_off is False
    assert tray.runtime_coordinator.stop_and_drain(timeout_s=1.0) is True


def test_init_handles_profile_migration_engine_fallback_and_permission_cb_failure(monkeypatch):
    import keyrgb.core.profile as profile_pkg

    calls = {"set_backend": 0, "start_power": 0, "start_polling": 0, "autostart": 0}

    class FakeConfig:
        effect = "wave"
        speed = 3
        brightness = 20

    class FakeEngine:
        def __init__(self, *, backend=None):
            if backend is not None:
                raise TypeError("backend not accepted")
            object.__setattr__(self, "backend_seen", None)

        def __setattr__(self, name, value):
            if name == "_permission_error_cb":
                raise RuntimeError("deny")
            object.__setattr__(self, name, value)

        def set_backend(self, backend):
            calls["set_backend"] += 1
            raise RuntimeError(f"cannot set {backend}")

    class FakePowerManager:
        pass

    fake_profiles = SimpleNamespace(
        migrate_builtin_profile_brightness=lambda _cfg: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    fake_pm = SimpleNamespace(stop_monitoring=lambda: None)

    monkeypatch.setattr(profile_pkg, "profiles", fake_profiles, raising=False)
    monkeypatch.setattr(app, "load_tray_dependencies", lambda: (FakeEngine, FakeConfig, FakePowerManager))
    monkeypatch.setattr(app, "select_backend_with_introspection", lambda: ("backend", "probe", {"caps": True}))
    monkeypatch.setattr(app, "select_device_discovery_snapshot", lambda: None)
    monkeypatch.setattr(app, "load_ite_dimensions", lambda: (6, 21))
    monkeypatch.setattr(
        app,
        "start_power_monitoring",
        lambda self, *, power_manager_cls, config: (
            calls.__setitem__("start_power", calls["start_power"] + 1) or fake_pm
        ),
    )
    monkeypatch.setattr(
        app,
        "start_all_polling",
        lambda self, *, ite_num_rows, ite_num_cols: calls.__setitem__("start_polling", calls["start_polling"] + 1),
    )
    monkeypatch.setattr(
        app,
        "maybe_autostart_effect",
        lambda self: calls.__setitem__("autostart", calls["autostart"] + 1),
    )

    tray = app.KeyRGBTray()

    assert isinstance(tray.config, FakeConfig)
    assert isinstance(tray.engine, FakeEngine)
    assert tray.power_manager is fake_pm
    assert calls == {"set_backend": 1, "start_power": 1, "start_polling": 1, "autostart": 1}
    assert tray.runtime_coordinator.stop_and_drain(timeout_s=1.0) is True


def test_init_failure_cleans_partially_started_runtime(monkeypatch):
    calls: list[object] = []

    class FakeConfig:
        tray_device_context = "keyboard"

    class FakeEngine:
        pass

    class FakePowerManager:
        pass

    fake_pm = SimpleNamespace()

    monkeypatch.setattr(app, "load_tray_dependencies", lambda: (FakeEngine, FakeConfig, FakePowerManager))
    monkeypatch.setattr(app, "select_backend_with_introspection", lambda: (None, None, None))
    monkeypatch.setattr(app, "select_device_discovery_snapshot", lambda: None)
    monkeypatch.setattr(app, "load_ite_dimensions", lambda: (6, 21))
    monkeypatch.setattr(app, "start_power_monitoring", lambda *_a, **_kw: fake_pm)
    monkeypatch.setattr(app, "start_all_polling", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("polling")))
    monkeypatch.setattr(
        app.app_lifecycle,
        "shutdown_tray_runtime_best_effort",
        lambda tray: (
            tray.runtime_coordinator.stop_and_drain(timeout_s=1.0),
            calls.append((tray.engine, tray.power_manager)),
        ),
    )

    with pytest.raises(RuntimeError, match="polling"):
        app.KeyRGBTray()

    assert len(calls) == 1
    engine, power_manager = calls[0]
    assert isinstance(engine, FakeEngine)
    assert power_manager is fake_pm


def test_refresh_ui_calls_instance_update_methods():
    calls = {"icon": 0, "menu": 0}

    class Dummy:
        def _update_icon(self):
            calls["icon"] += 1

        def _update_menu(self):
            calls["menu"] += 1

    dummy = Dummy()
    app.KeyRGBTray._refresh_ui(dummy)

    assert calls == {"icon": 1, "menu": 1}


def test_refresh_ui_can_disable_icon_animation():
    calls = {"animate": None, "menu": 0}

    class Dummy:
        def _update_icon(self, *, animate=True):
            calls["animate"] = animate

        def _update_menu(self):
            calls["menu"] += 1

    dummy = Dummy()
    app.KeyRGBTray._refresh_ui(dummy, animate_icon=False)

    assert calls == {"animate": False, "menu": 1}


def test_refresh_ui_can_skip_live_menu_rebuild():
    calls = {"animate": None, "menu": 0}

    class Dummy:
        def _update_icon(self, *, animate=True):
            calls["animate"] = animate

        def _update_menu(self):
            calls["menu"] += 1

    dummy = Dummy()
    app.KeyRGBTray._refresh_ui(dummy, animate_icon=False, refresh_menu=False)

    assert calls == {"animate": False, "menu": 0}
