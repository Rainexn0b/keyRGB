from types import SimpleNamespace

import pytest

import src.tray.app.application as app


def test_init_wires_dependencies_and_starts_pollers(monkeypatch):
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
        calls["start_polling"] += 1
        assert ite_num_rows == 6
        assert ite_num_cols == 21

    def _maybe_autostart_effect(self):
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

    assert isinstance(tray.config, FakeConfig)
    assert isinstance(tray.engine, FakeEngine)
    assert tray.engine.backend == "backend"
    assert tray.power_manager is fake_pm
    assert tray.backend == "backend"
    assert tray.backend_probe == "probe"
    assert tray.backend_caps == {"caps": True}
    assert tray.device_discovery == {"candidates": [{"device_type": "lightbar"}]}
    assert tray.selected_device_context == "lightbar:048d:7001"


def test_init_handles_profile_migration_engine_fallback_and_permission_cb_failure(monkeypatch):
    import src.core.profile as profile_pkg

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


def test_log_event_propagates_unexpected_source_action_string_errors(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(
        app.logger,
        "info",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("logged")),
    )

    class BadStr:
        def __str__(self):
            raise AssertionError("unexpected string bug")

    with pytest.raises(AssertionError, match="unexpected string bug"):
        app.KeyRGBTray._log_event(tray, BadStr(), "act", x=1)


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


def test_log_event_propagates_unexpected_field_repr_errors(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda *_a, **_k: None)

    class _Unrepr:
        def __repr__(self):
            raise AssertionError("unexpected repr bug")

    with pytest.raises(AssertionError, match="unexpected repr bug"):
        app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)


def test_log_event_propagates_unexpected_throttle_state_errors(monkeypatch):
    logged = []

    class BadMap(dict):
        def get(self, *_a, **_k):
            raise AssertionError("unexpected throttle bug")

    tray = SimpleNamespace(_event_last_at=BadMap())

    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    with pytest.raises(AssertionError, match="unexpected throttle bug"):
        app.KeyRGBTray._log_event(tray, "src", "act", a=1)


def test_log_event_propagates_unexpected_logger_failures(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("unexpected logger bug")))

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        app.KeyRGBTray._log_event(tray, "src", "act", a=1)


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
    calls = {"render": 0, "menu": 0, "run": 0}

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

    def _create_icon_for_state(*, config, is_off, now=None, backend=None):
        calls["render"] += 1
        assert config.effect == "perkey"
        assert is_off is False
        assert backend is tray.backend
        return "IMAGE"

    def _build_menu(self, *, pystray, item):
        calls["menu"] += 1
        assert pystray is fake_pystray
        assert item is fake_item
        return "MENU"

    monkeypatch.setattr(app.icon_mod, "create_icon_for_state", _create_icon_for_state)
    monkeypatch.setattr(app.menu_mod, "build_menu", _build_menu)

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="perkey", speed=4, brightness=5),
        is_off=False,
        icon=None,
        backend=object(),
    )

    app.KeyRGBTray.run(tray)

    assert isinstance(tray.icon, FakeIcon)
    assert tray.icon.name == "keyrgb"
    assert tray.icon.image == "IMAGE"
    assert tray.icon.title == "KeyRGB"
    assert tray.icon.menu == "MENU"
    assert calls == {"render": 1, "menu": 1, "run": 1}


def test_run_flushes_queued_notifications(monkeypatch):
    flushed = []

    class FakeIcon:
        def __init__(self, *_args, **_kwargs):
            pass

        def run(self):
            return None

    fake_pystray = SimpleNamespace(Icon=FakeIcon)
    fake_item = object()

    monkeypatch.setattr(app.runtime, "get_pystray", lambda: (fake_pystray, fake_item))
    monkeypatch.setattr(app.icon_mod, "create_icon_for_state", lambda **_kwargs: "IMAGE")
    monkeypatch.setattr(app.menu_mod, "build_menu", lambda *_args, **_kwargs: "MENU")

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="perkey", speed=4, brightness=5),
        is_off=False,
        icon=None,
        backend=object(),
        _pending_notifications=[("Title 1", "Body 1"), ("Title 2", "Body 2")],
        _notify=lambda title, message: flushed.append((title, message)),
    )

    app.KeyRGBTray.run(tray)

    assert flushed == [("Title 1", "Body 1"), ("Title 2", "Body 2")]
    assert tray._pending_notifications == []


def test_notify_queues_early_notifications_without_icon() -> None:
    tray = SimpleNamespace(icon=None, _pending_notifications=[])

    app.KeyRGBTray._notify(tray, "Title", "Body")

    assert tray._pending_notifications == [("Title", "Body")]


def test_notify_uses_icon_notify_with_two_or_one_argument_fallback() -> None:
    two_arg_calls = []

    tray = SimpleNamespace(
        icon=SimpleNamespace(notify=lambda message, title: two_arg_calls.append((title, message))),
        _pending_notifications=[],
    )
    app.KeyRGBTray._notify(tray, "Title", "Body")
    assert two_arg_calls == [("Title", "Body")]

    one_arg_calls = []

    def _notify_one_arg(message, title=None):
        if title is not None:
            raise TypeError("one arg only")
        one_arg_calls.append(message)

    tray = SimpleNamespace(icon=SimpleNamespace(notify=_notify_one_arg), _pending_notifications=[])
    app.KeyRGBTray._notify(tray, "Title", "Body")

    assert one_arg_calls == ["Body"]


def test_notify_propagates_unexpected_one_arg_fallback_errors() -> None:
    def _notify_one_arg(message, title=None):
        if title is not None:
            raise TypeError("one arg only")
        raise AssertionError("unexpected notification bug")

    tray = SimpleNamespace(icon=SimpleNamespace(notify=_notify_one_arg), _pending_notifications=[])

    with pytest.raises(AssertionError, match="unexpected notification bug"):
        app.KeyRGBTray._notify(tray, "Title", "Body")


def test_notify_falls_back_to_notify_send_when_icon_notify_fails(monkeypatch):
    commands = []
    tray = SimpleNamespace(
        icon=SimpleNamespace(notify=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("nope"))),
        _pending_notifications=[],
    )

    monkeypatch.setattr(app.shutil, "which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None)
    monkeypatch.setattr(app.subprocess, "run", lambda cmd, **kwargs: commands.append((cmd, kwargs)))

    app.KeyRGBTray._notify(tray, "Title", "Body")

    assert commands == [
        (
            ["notify-send", "Title", "Body"],
            {
                "check": False,
                "stdout": app.subprocess.DEVNULL,
                "stderr": app.subprocess.DEVNULL,
            },
        )
    ]


def test_notify_permission_issue_reports_once_and_includes_backend_hint(monkeypatch):
    warnings = []
    notifications = []
    tray = SimpleNamespace(
        _permission_notice_sent=False,
        backend=SimpleNamespace(name="ite8291r3"),
        _notify=lambda title, message: notifications.append((title, message)),
    )
    err = PermissionError("denied")

    monkeypatch.setattr(app, "is_permission_denied", lambda exc: exc is err)
    monkeypatch.setattr(app.logger, "warning", lambda fmt, exc: warnings.append((fmt, exc)))

    app.KeyRGBTray._notify_permission_issue(tray, err)
    app.KeyRGBTray._notify_permission_issue(tray, err)

    assert tray._permission_notice_sent is True
    assert warnings == [("Permission issue while applying lighting: %s", err)]
    assert len(notifications) == 1
    title, message = notifications[0]
    assert title == "KeyRGB: Permission denied"
    assert "99-ite8291-wootbook.rules" in message
    assert "https://github.com/Rainexn0b/keyRGB" in message


def test_notify_permission_issue_ignores_non_permission_errors(monkeypatch):
    notifications = []
    tray = SimpleNamespace(
        _permission_notice_sent=False,
        backend=SimpleNamespace(name="sysfs-leds"),
        _notify=lambda title, message: notifications.append((title, message)),
    )

    monkeypatch.setattr(app, "is_permission_denied", lambda exc: False)

    app.KeyRGBTray._notify_permission_issue(tray, RuntimeError("other"))

    assert tray._permission_notice_sent is False
    assert notifications == []


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
        lambda _self, animate=True: calls.__setitem__("icon", calls["icon"] + 1),
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
        ("_on_device_context_clicked", "on_device_context_clicked", ("lightbar:048d:7001",)),
        ("_on_selected_device_color_clicked", "on_selected_device_color_clicked", (None, None)),
        ("_on_selected_device_brightness_clicked", "on_selected_device_brightness_clicked", (None, "ITEM")),
        ("_on_selected_device_turn_off_clicked", "on_selected_device_turn_off_clicked", (None, None)),
        ("_on_off_clicked", "on_off_clicked", (None, None)),
        ("_on_turn_on_clicked", "on_turn_on_clicked", (None, None)),
        ("_on_hardware_static_mode_clicked", "on_hardware_static_mode_clicked", (None, None)),
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
        ("_on_support_debug_clicked", "on_support_debug_clicked"),
        ("_on_backend_discovery_clicked", "on_backend_discovery_clicked"),
        ("_on_tcc_profiles_gui_clicked", "on_tcc_profiles_gui_clicked"),
    ],
)
def test_callback_wrapper_methods_delegate_without_self(monkeypatch, method_name, cb_attr):
    calls = {"n": 0}
    monkeypatch.setattr(app.callbacks, cb_attr, lambda: calls.__setitem__("n", calls["n"] + 1))
    tray = SimpleNamespace()

    getattr(app.KeyRGBTray, method_name)(tray, None, None)
    assert calls == {"n": 1}
