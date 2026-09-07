import os
import sys
from types import SimpleNamespace

import pytest

from keyrgb.tray.integrations import runtime


@pytest.fixture(autouse=True)
def _reset_runtime_singletons(monkeypatch):
    runtime._pystray_mod = None
    runtime._pystray_item = None
    runtime._gtk_log_handler_id = None
    runtime._appindicator_log_handler_id = None
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)


def test_clear_failed_import_removes_partial_module():
    previous = sys.modules.get("pystray")
    sentinel = object()
    sys.modules["pystray"] = sentinel
    try:
        runtime._clear_failed_import("pystray")
        assert "pystray" not in sys.modules
    finally:
        if previous is not None:
            sys.modules["pystray"] = previous
        else:
            sys.modules.pop("pystray", None)


def test_classify_pystray_import_error_broken_gi_in_cause_chain():
    inner = AttributeError("module 'gi' has no attribute 'require_version'")
    outer = ImportError("pystray import failed")
    outer.__cause__ = inner

    failure = runtime._classify_pystray_import_error(outer)

    assert failure is not None
    assert failure.reason == "broken-gi"
    assert failure.original is outer


def test_iter_exc_chain_breaks_on_self_referential_cause():
    exc = RuntimeError("boom")
    exc.__cause__ = exc
    chain = list(runtime._iter_exc_chain(exc))
    assert chain == [exc]


def test_classify_pystray_import_error_returns_none_when_unrecognized():
    exc = RuntimeError("some other failure")
    assert runtime._classify_pystray_import_error(exc) is None


def test_set_pystray_backend_xorg_for_retry_overrides(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "appindicator")
    runtime._set_pystray_backend_xorg_for_retry()
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"


def test_set_pystray_backend_gtk_for_retry_overrides(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "xorg")
    runtime._set_pystray_backend_gtk_for_retry()
    assert os.environ.get("PYSTRAY_BACKEND") == "gtk"


def test_set_pystray_backend_appindicator_for_retry_overrides(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "xorg")
    runtime._set_pystray_backend_appindicator_for_retry()
    assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"


def test_is_kde_wayland_session_true_for_plasma(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setenv("DESKTOP_SESSION", "/usr/share/wayland-sessions/plasma.desktop")
    assert runtime._is_kde_wayland_session() is True


def test_is_kde_wayland_session_false_outside_kde_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("DESKTOP_SESSION", "gnome")
    assert runtime._is_kde_wayland_session() is False


def test_install_gtk_scale_factor_log_filter_registers_once(monkeypatch):
    calls = {"log_set_handler": 0, "require_version": []}

    fake_glib = SimpleNamespace(
        LogLevelFlags=SimpleNamespace(LEVEL_CRITICAL=123),
        log_default_handler=lambda *_args: None,
        log_set_handler=lambda domain, level, handler, user_data: (
            calls.update(log_set_handler=calls["log_set_handler"] + 1) or 99
        ),
    )

    def _fake_import_module(name: str):
        if name == "gi":
            return SimpleNamespace(
                require_version=lambda namespace, version: calls["require_version"].append((namespace, version))
            )
        if name == "gi.repository.GLib":
            return fake_glib
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(runtime.importlib, "import_module", _fake_import_module)

    runtime._install_gtk_scale_factor_log_filter()
    runtime._install_gtk_scale_factor_log_filter()

    assert calls["require_version"] == [("GLib", "2.0")]
    assert calls["log_set_handler"] == 1
    assert runtime._gtk_log_handler_id == 99


def test_install_appindicator_deprecation_log_filter_registers_once(monkeypatch):
    calls = {"log_set_handler": 0, "require_version": []}

    fake_glib = SimpleNamespace(
        LogLevelFlags=SimpleNamespace(LEVEL_WARNING=16),
        log_default_handler=lambda *_args: None,
        log_set_handler=lambda domain, level, handler, user_data: (
            calls.update(log_set_handler=calls["log_set_handler"] + 1) or 199
        ),
    )

    def _fake_import_module(name: str):
        if name == "gi":
            return SimpleNamespace(
                require_version=lambda namespace, version: calls["require_version"].append((namespace, version))
            )
        if name == "gi.repository.GLib":
            return fake_glib
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(runtime.importlib, "import_module", _fake_import_module)

    runtime._install_appindicator_deprecation_log_filter()
    runtime._install_appindicator_deprecation_log_filter()

    assert calls["require_version"] == [("GLib", "2.0")]
    assert calls["log_set_handler"] == 1
    assert runtime._appindicator_log_handler_id == 199


def test_install_log_filter_for_backend_routes_to_expected_filter(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: calls.append("gtk"))
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: calls.append("appindicator"))

    runtime._install_log_filter_for_backend("gtk")
    runtime._install_log_filter_for_backend("appindicator")
    runtime._install_log_filter_for_backend("xorg")

    assert calls == ["gtk", "appindicator"]


def test_configure_backend_for_import_sets_env_and_installs_filter(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(runtime, "_install_log_filter_for_backend", lambda backend: calls.append(backend))

    runtime._configure_backend_for_import("gtk")
    assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
    runtime._configure_backend_for_import("appindicator")
    assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
    runtime._configure_backend_for_import("xorg")
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"

    assert calls == ["gtk", "appindicator", "xorg"]


def test_auto_backend_candidates_prefers_kde_wayland_appindicator(monkeypatch):
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: True)
    assert runtime._auto_backend_candidates(gi_working=True) == [
        ("appindicator", "appindicator (auto-kde-wayland)"),
        ("gtk", "gtk (appindicator fallback)"),
        ("xorg", "xorg (gtk fallback)"),
    ]


def test_auto_backend_candidates_prefers_gtk_when_gi_works(monkeypatch):
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: False)
    assert runtime._auto_backend_candidates(gi_working=True) == [
        ("gtk", "gtk (auto)"),
        ("xorg", "xorg (gtk fallback)"),
        ("appindicator", "appindicator (xorg fallback)"),
    ]


def test_auto_backend_candidates_prefers_xorg_without_gi(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_is_kde_wayland_session",
        lambda: (_ for _ in ()).throw(AssertionError("checked kde wayland")),
    )
    assert runtime._auto_backend_candidates(gi_working=False) == [("xorg", "xorg (auto)")]


def test_is_gnome_session_true_when_xdg_current_desktop_contains_gnome(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    assert runtime._is_gnome_session() is True


def test_is_gnome_session_true_when_desktop_session_is_gnome(monkeypatch):
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.setenv("DESKTOP_SESSION", "gnome")
    assert runtime._is_gnome_session() is True


def test_is_gnome_session_false_on_kde_plasma(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setenv("DESKTOP_SESSION", "/usr/share/wayland-sessions/plasma.desktop")
    assert runtime._is_gnome_session() is False


def test_is_gnome_session_false_when_env_unset(monkeypatch):
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    assert runtime._is_gnome_session() is False


def test_auto_backend_candidates_prefers_appindicator_on_gnome(monkeypatch):
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: True)
    assert runtime._auto_backend_candidates(gi_working=True) == [
        ("appindicator", "appindicator (auto-gnome)"),
        ("gtk", "gtk (appindicator fallback)"),
        ("xorg", "xorg (gtk fallback)"),
    ]


def test_import_pystray_with_fallbacks_tries_candidates_in_order(monkeypatch):
    calls: list[str] = []

    def _fake_configure(backend: str) -> None:
        calls.append(f"configure:{backend}")

    def _fake_clear(_name: str) -> None:
        calls.append("clear")

    def _fake_import_module(name: str):
        assert name == "pystray"
        backend = os.environ.get("PYSTRAY_BACKEND")
        calls.append(f"import:{backend}")
        if backend == "gtk":
            raise RuntimeError("gtk failed")
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(runtime, "_configure_backend_for_import", _fake_configure)
    monkeypatch.setattr(runtime, "_clear_failed_import", _fake_clear)

    def _fake_configure_with_env(backend: str) -> None:
        os.environ["PYSTRAY_BACKEND"] = backend
        _fake_configure(backend)

    monkeypatch.setattr(runtime, "_configure_backend_for_import", _fake_configure_with_env)

    mod = runtime._import_pystray_with_fallbacks(
        [("gtk", "gtk (auto)"), ("xorg", "xorg (gtk fallback)")],
        import_module=_fake_import_module,
    )

    assert hasattr(mod, "MenuItem")
    assert calls == ["configure:gtk", "import:gtk", "clear", "configure:xorg", "import:xorg"]


def test_gi_is_working_false_when_missing(monkeypatch):
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: None)
    assert runtime._gi_is_working() is False


def test_gi_is_working_true_when_require_version_present(monkeypatch):
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        runtime.importlib,
        "import_module",
        lambda name: SimpleNamespace(require_version=lambda *a, **k: None),
    )
    assert runtime._gi_is_working() is True


def test_gi_is_working_false_when_import_or_attribute_fails(monkeypatch):
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: SimpleNamespace())
    assert runtime._gi_is_working() is False

    def _boom(_name):
        raise RuntimeError("nope")

    monkeypatch.setattr(runtime.importlib, "import_module", _boom)
    assert runtime._gi_is_working() is False
