from types import SimpleNamespace

import pytest

import keyrgb.tray.app.application as app


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


def test_run_passes_explicit_runtime_state_to_bindings(monkeypatch):
    tray = SimpleNamespace()
    sentinel_state = object()
    seen = {}

    monkeypatch.setattr(
        app.application_bindings,
        "build_tray_run_state",
        lambda _tray: sentinel_state,
    )

    def _run_tray(_tray, *, bindings, state=None):
        seen["tray"] = _tray
        seen["bindings"] = bindings
        seen["state"] = state

    monkeypatch.setattr(app.application_bindings, "run_tray", _run_tray)

    app.KeyRGBTray.run(tray)

    assert seen["tray"] is tray
    assert seen["state"] is sentinel_state
    assert isinstance(seen["bindings"], app.application_bindings.TrayRunBindings)


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


@pytest.mark.parametrize("backend_name", ["ite8291r3_perkey", "ite8258_zones_lenovo_legion", "ite8258_perkey_chassis"])
def test_notify_permission_issue_reports_once_and_includes_backend_hint(monkeypatch, backend_name):
    warnings = []
    notifications = []
    tray = SimpleNamespace(
        _permission_notice_sent=False,
        backend=SimpleNamespace(name=backend_name),
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


def test_on_quit_clicked_closes_secondary_cache_stops_power_engine_and_icon(monkeypatch):
    import threading

    calls = {"pm": 0, "cache": 0, "engine": 0, "icon": 0}
    icon_stopped = threading.Event()

    tray = SimpleNamespace(
        power_manager=SimpleNamespace(stop_monitoring=lambda: calls.__setitem__("pm", calls["pm"] + 1)),
        engine=SimpleNamespace(stop=lambda: calls.__setitem__("engine", calls["engine"] + 1)),
    )

    def stop_icon() -> None:
        calls["icon"] += 1
        icon_stopped.set()

    icon = SimpleNamespace(stop=stop_icon)
    monkeypatch.setattr(
        "keyrgb.tray.controllers.software_target_controller.close_secondary_software_target_cache",
        lambda _tray: calls.__setitem__("cache", calls["cache"] + 1),
    )

    app.KeyRGBTray._on_quit_clicked(tray, icon, None)

    assert icon_stopped.wait(timeout=1.0)
    assert calls == {"pm": 1, "cache": 1, "engine": 1, "icon": 1}


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


def test_refresh_system_power_view_delegate_refreshes_snapshot_and_menu(monkeypatch):
    calls = []
    tray = SimpleNamespace(_update_menu=lambda: calls.append("menu"))
    status = object()

    monkeypatch.setattr(
        app,
        "refresh_system_power_snapshot",
        lambda _self: (calls.append("snapshot"), status)[1],
    )

    observed = app.KeyRGBTray._refresh_system_power_view(tray)
    # Snapshot must be stored before the menu rebuild is requested so the
    # rebuilt menu renders the fresh mode.
    assert calls == ["snapshot", "menu"]
    assert observed is status


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
        ("_on_selected_device_turn_on_clicked", "on_selected_device_turn_on_clicked", (None, None)),
        ("_on_off_clicked", "on_off_clicked", (None, None)),
        ("_on_turn_on_clicked", "on_turn_on_clicked", (None, None)),
        ("_on_perkey_clicked", "on_perkey_clicked", (None, None)),
        ("_on_hardware_static_mode_clicked", "on_hardware_static_mode_clicked", (None, None)),
        ("_on_hardware_color_clicked", "on_hardware_color_clicked", (None, None)),
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
        ("_on_tuxedo_gui_clicked", "on_uniform_gui_clicked"),
        ("_on_reactive_color_clicked", "on_reactive_color_gui_clicked"),
        ("_on_power_settings_clicked", "on_power_settings_clicked"),
        ("_on_power_mode_settings_clicked", "on_power_mode_settings_clicked"),
        ("_on_support_debug_clicked", "on_support_debug_clicked"),
        ("_on_backend_discovery_clicked", "on_backend_discovery_clicked"),
    ],
)
def test_callback_wrapper_methods_delegate_without_self(monkeypatch, method_name, cb_attr):
    calls = {"n": 0}
    monkeypatch.setattr(app.callbacks, cb_attr, lambda: calls.__setitem__("n", calls["n"] + 1))
    tray = SimpleNamespace()

    getattr(app.KeyRGBTray, method_name)(tray, None, None)
    assert calls == {"n": 1}
