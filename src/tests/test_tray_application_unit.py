from types import SimpleNamespace

import pytest

import src.tray.app.application as app


def test_init_wires_dependencies_and_starts_pollers(monkeypatch):
    calls = {
        "deps": 0,
        "select_backend": 0,
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

    class FakeEngine:
        def __init__(self):
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

    def _start_power_monitoring(self, *, power_manager_cls, config):
        calls["start_power"] += 1
        assert power_manager_cls is FakePowerManager
        assert isinstance(config, FakeConfig)
        assert self.config is config
        return fake_pm

    def _start_all_polling(self, *, ite_num_rows, ite_num_cols):
        calls["start_polling"] += 1
        assert ite_num_rows == 6
        assert ite_num_cols == 21

    def _maybe_autostart_effect(self):
        calls["autostart"] += 1

    monkeypatch.setattr(app, "load_tray_dependencies", _load_tray_dependencies)
    monkeypatch.setattr(app, "select_backend_with_introspection", _select_backend_with_introspection)
    monkeypatch.setattr(app, "load_ite_dimensions", _load_ite_dimensions)
    monkeypatch.setattr(app, "start_power_monitoring", _start_power_monitoring)
    monkeypatch.setattr(app, "start_all_polling", _start_all_polling)
    monkeypatch.setattr(app, "maybe_autostart_effect", _maybe_autostart_effect)

    tray = app.KeyRGBTray()

    assert calls == {
        "deps": 1,
        "select_backend": 1,
        "dimensions": 1,
        "start_power": 1,
        "start_polling": 1,
        "autostart": 1,
    }

    assert isinstance(tray.config, FakeConfig)
    assert isinstance(tray.engine, FakeEngine)
    assert tray.power_manager is fake_pm
    assert tray.backend == "backend"
    assert tray.backend_probe == "probe"
    assert tray.backend_caps == {"caps": True}


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


def test_log_event_formats_fields_sorted_and_throttles(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    logged = []

    times = iter([10.0, 10.2, 11.5])
    monkeypatch.setattr(app.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    class _Unrepr:
        def __repr__(self):
            raise RuntimeError("no repr")

    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)
    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)  # throttled
    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)  # allowed

    assert len(logged) == 2
    assert logged[0].startswith("EVENT config:apply")
    # Fields are sorted and unrepr is handled.
    assert "a=1" in logged[0]
    assert "b=<unrepr>" in logged[0]


def test_log_event_bails_out_if_source_action_not_stringable(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(
        app.logger,
        "info",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("logged")),
    )

    class BadStr:
        def __str__(self):
            raise RuntimeError("no")

    app.KeyRGBTray._log_event(tray, BadStr(), BadStr(), x=1)


def test_log_event_logs_even_if_throttle_state_errors(monkeypatch):
    logged = []

    class BadMap(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("nope")

        def __setitem__(self, *_a, **_k):
            raise RuntimeError("nope")

    tray = SimpleNamespace(_event_last_at=BadMap())

    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    app.KeyRGBTray._log_event(tray, "src", "act", a=1)
    assert logged == ["EVENT src:act a=1"]


def test_log_event_swallows_logger_failures(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no")))

    # Should not raise.
    app.KeyRGBTray._log_event(tray, "src", "act", a=1)


def test_log_exception_delegates_to_logger_exception(monkeypatch):
    calls = []

    def _exc(msg, exc):
        calls.append((msg, exc))

    monkeypatch.setattr(app.logger, "exception", _exc)
    tray = SimpleNamespace()
    err = RuntimeError("boom")

    app.KeyRGBTray._log_exception(tray, "hello", err)
    assert calls == [("hello", err)]


def test_run_builds_icon_and_runs_without_real_pystray(monkeypatch):
    calls = {"rep": 0, "create": 0, "menu": 0, "run": 0}

    class FakeIcon:
        def __init__(self, name, image, title, menu):
            self.name = name
            self.image = image
            self.title = title
            self.menu = menu

        def run(self):
            calls["run"] += 1

        def stop(self):
            pass

    fake_pystray = SimpleNamespace(Icon=FakeIcon)
    fake_item = object()

    monkeypatch.setattr(app.runtime, "get_pystray", lambda: (fake_pystray, fake_item))

    def _rep_color(*, config, is_off):
        calls["rep"] += 1
        assert config.effect == "perkey"
        assert is_off is False
        return (1, 2, 3)

    def _create_icon(color):
        calls["create"] += 1
        assert color == (1, 2, 3)
        return "IMAGE"

    def _build_menu(self, *, pystray, item):
        calls["menu"] += 1
        assert pystray is fake_pystray
        assert item is fake_item
        return "MENU"

    monkeypatch.setattr(app.icon_mod, "representative_color", _rep_color)
    monkeypatch.setattr(app.icon_mod, "create_icon", _create_icon)
    monkeypatch.setattr(app.menu_mod, "build_menu", _build_menu)

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="perkey", speed=4, brightness=5),
        is_off=False,
        icon=None,
    )

    app.KeyRGBTray.run(tray)

    assert isinstance(tray.icon, FakeIcon)
    assert tray.icon.name == "keyrgb"
    assert tray.icon.image == "IMAGE"
    assert tray.icon.title == "KeyRGB"
    assert tray.icon.menu == "MENU"
    assert calls == {"rep": 1, "create": 1, "menu": 1, "run": 1}


def test_on_quit_clicked_stops_power_engine_and_icon():
    calls = {"pm": 0, "engine": 0, "icon": 0}

    tray = SimpleNamespace(
        power_manager=SimpleNamespace(stop_monitoring=lambda: calls.__setitem__("pm", calls["pm"] + 1)),
        engine=SimpleNamespace(stop=lambda: calls.__setitem__("engine", calls["engine"] + 1)),
    )
    icon = SimpleNamespace(stop=lambda: calls.__setitem__("icon", calls["icon"] + 1))

    app.KeyRGBTray._on_quit_clicked(tray, icon, None)

    assert calls == {"pm": 1, "engine": 1, "icon": 1}


def test_update_icon_and_menu_delegate_to_refresh_helpers(monkeypatch):
    calls = {"icon": 0, "menu": 0}
    tray = SimpleNamespace()

    monkeypatch.setattr(
        app,
        "update_tray_icon",
        lambda _self: calls.__setitem__("icon", calls["icon"] + 1),
    )
    monkeypatch.setattr(
        app,
        "update_tray_menu",
        lambda _self: calls.__setitem__("menu", calls["menu"] + 1),
    )

    app.KeyRGBTray._update_icon(tray)
    app.KeyRGBTray._update_menu(tray)
    assert calls == {"icon": 1, "menu": 1}


def test_effect_and_power_wrappers_delegate(monkeypatch):
    calls = {"start": 0, "off": 0, "restore": 0, "policy": []}
    tray = SimpleNamespace()

    monkeypatch.setattr(
        app,
        "start_current_effect",
        lambda _self: calls.__setitem__("start", calls["start"] + 1),
    )
    monkeypatch.setattr(app, "power_turn_off", lambda _self: calls.__setitem__("off", calls["off"] + 1))
    monkeypatch.setattr(
        app,
        "power_restore",
        lambda _self: calls.__setitem__("restore", calls["restore"] + 1),
    )
    monkeypatch.setattr(
        app,
        "apply_brightness_from_power_policy",
        lambda _self, b: calls["policy"].append(b),
    )

    app.KeyRGBTray._start_current_effect(tray)
    app.KeyRGBTray.turn_off(tray)
    app.KeyRGBTray.restore(tray)
    app.KeyRGBTray.apply_brightness_from_power_policy(tray, 7)

    assert calls == {"start": 1, "off": 1, "restore": 1, "policy": [7]}


@pytest.mark.parametrize(
    "method_name,cb_attr,args",
    [
        ("_on_effect_clicked", "on_effect_clicked", (None, "ITEM")),
        ("_on_effect_key_clicked", "on_effect_key_clicked", ("perkey",)),
        ("_on_speed_clicked", "on_speed_clicked_cb", (None, "ITEM")),
        ("_on_brightness_clicked", "on_brightness_clicked_cb", (None, "ITEM")),
        ("_on_off_clicked", "on_off_clicked", (None, None)),
        ("_on_turn_on_clicked", "on_turn_on_clicked", (None, None)),
        ("_on_hardware_color_clicked", "on_hardware_color_clicked", (None, None)),
        ("_on_tcc_profile_clicked", "on_tcc_profile_clicked", ("silent",)),
    ],
)
def test_callback_wrapper_methods_delegate(monkeypatch, method_name, cb_attr, args):
    received = []

    def _cb(*cb_args):
        received.append(cb_args)

    monkeypatch.setattr(app.callbacks, cb_attr, _cb)
    tray = SimpleNamespace()

    getattr(app.KeyRGBTray, method_name)(tray, *args)

    # Wrappers that include self pass it as the first callback arg.
    assert received
    assert received[0][0] is tray


@pytest.mark.parametrize(
    "method_name,cb_attr",
    [
        ("_on_perkey_clicked", "on_perkey_clicked"),
        ("_on_tuxedo_gui_clicked", "on_uniform_gui_clicked"),
        ("_on_reactive_color_clicked", "on_reactive_color_gui_clicked"),
        ("_on_power_settings_clicked", "on_power_settings_clicked"),
        ("_on_tcc_profiles_gui_clicked", "on_tcc_profiles_gui_clicked"),
    ],
)
def test_callback_wrapper_methods_delegate_without_self(monkeypatch, method_name, cb_attr):
    calls = {"n": 0}
    monkeypatch.setattr(app.callbacks, cb_attr, lambda: calls.__setitem__("n", calls["n"] + 1))
    tray = SimpleNamespace()

    getattr(app.KeyRGBTray, method_name)(tray, None, None)
    assert calls == {"n": 1}
