import importlib
import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

import src.tray.integrations.runtime as runtime


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
        log_set_handler=lambda domain, level, handler, user_data: calls.update(log_set_handler=calls["log_set_handler"] + 1)
        or 99,
    )

    def _fake_import_module(name: str):
        if name == "gi":
            return SimpleNamespace(require_version=lambda namespace, version: calls["require_version"].append((namespace, version)))
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
        log_set_handler=lambda domain, level, handler, user_data: calls.update(log_set_handler=calls["log_set_handler"] + 1)
        or 199,
    )

    def _fake_import_module(name: str):
        if name == "gi":
            return SimpleNamespace(require_version=lambda namespace, version: calls["require_version"].append((namespace, version)))
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


def test_get_pystray_returns_cached_without_import():
    sentinel_mod = object()
    sentinel_item = object()
    runtime._pystray_mod = sentinel_mod
    runtime._pystray_item = sentinel_item

    # If this path accidentally imports, the test will blow up.
    original_import_module = importlib.import_module
    importlib.import_module = lambda _name: (_ for _ in ()).throw(AssertionError("imported"))
    try:
        mod, item = runtime.get_pystray()
        assert mod is sentinel_mod
        assert item is sentinel_item
    finally:
        importlib.import_module = original_import_module


def test_get_pystray_explicit_backend_does_not_probe_gi(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "xorg")
    monkeypatch.setattr(
        runtime,
        "_gi_is_working",
        lambda: (_ for _ in ()).throw(AssertionError("probed gi")),
    )

    calls = {"import": 0, "log": []}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        return SimpleNamespace(MenuItem=object())

    def _fake_log(msg, *args):
        calls["log"].append((msg, args))

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)
    monkeypatch.setattr(runtime.logger, "info", _fake_log)

    mod, item = runtime.get_pystray()
    assert hasattr(mod, "MenuItem")
    assert item is getattr(mod, "MenuItem")
    assert calls["import"] == 1
    assert any("(explicit)" in m for (m, _a) in calls["log"])


def test_get_pystray_prefers_gtk_when_gi_works(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: False)
    install_calls = []
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(
        runtime,
        "_install_appindicator_deprecation_log_filter",
        lambda: (_ for _ in ()).throw(AssertionError("installed appindicator filter")),
    )
    calls = {"import": 0, "log": []}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)
    monkeypatch.setattr(runtime.logger, "info", lambda msg, *args: calls["log"].append((msg, args)))

    mod, item = runtime.get_pystray()
    assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
    assert calls["import"] == 1
    assert ("pystray backend: %s", ("gtk (auto)",)) in calls["log"]
    assert install_calls == [True]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_prefers_xorg_when_gi_is_unavailable(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: False)
    monkeypatch.setattr(
        runtime,
        "_install_gtk_scale_factor_log_filter",
        lambda: (_ for _ in ()).throw(AssertionError("installed gtk filter")),
    )
    monkeypatch.setattr(
        runtime,
        "_install_appindicator_deprecation_log_filter",
        lambda: (_ for _ in ()).throw(AssertionError("installed appindicator filter")),
    )

    calls = {"import": 0, "log": []}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)
    monkeypatch.setattr(runtime.logger, "info", lambda msg, *args: calls["log"].append((msg, args)))

    mod, item = runtime.get_pystray()
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"
    assert calls["import"] == 1
    assert ("pystray backend: %s", ("xorg (auto)",)) in calls["log"]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_falls_back_to_xorg_when_gtk_import_fails(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: False)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: None)
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: None)

    previous = sys.modules.get("pystray")
    sentinel_partial = object()
    sys.modules["pystray"] = sentinel_partial

    calls = {"import": 0}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        if calls["import"] == 1:
            assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
            raise RuntimeError("gtk backend failed")
        assert os.environ.get("PYSTRAY_BACKEND") == "xorg"
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)

    try:
        mod, item = runtime.get_pystray()
        assert calls["import"] == 2
        assert os.environ.get("PYSTRAY_BACKEND") == "xorg"
        assert item is getattr(mod, "MenuItem")
        assert sys.modules.get("pystray") is not sentinel_partial
    finally:
        if previous is not None:
            sys.modules["pystray"] = previous
        else:
            sys.modules.pop("pystray", None)


def test_get_pystray_falls_back_to_appindicator_when_gtk_and_xorg_import_fail(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: False)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: None)
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: None)

    previous = sys.modules.get("pystray")
    sentinel_partial = object()
    sys.modules["pystray"] = sentinel_partial

    calls = {"import": 0}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        if calls["import"] == 1:
            assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
            raise RuntimeError("gtk backend failed")
        if calls["import"] == 2:
            assert os.environ.get("PYSTRAY_BACKEND") == "xorg"
            raise RuntimeError("xorg backend failed")
        assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)

    try:
        mod, item = runtime.get_pystray()
        assert calls["import"] == 3
        assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
        assert item is getattr(mod, "MenuItem")
        assert sys.modules.get("pystray") is not sentinel_partial
    finally:
        if previous is not None:
            sys.modules["pystray"] = previous
        else:
            sys.modules.pop("pystray", None)


def test_get_pystray_explicit_gtk_installs_log_filter(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "gtk")
    install_calls = []
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(importlib, "import_module", lambda name: SimpleNamespace(MenuItem=object()))

    mod, item = runtime.get_pystray()

    assert install_calls == [True]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_prefers_appindicator_on_kde_wayland(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: True)
    install_calls = []
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(
        runtime,
        "_install_gtk_scale_factor_log_filter",
        lambda: (_ for _ in ()).throw(AssertionError("installed gtk filter")),
    )
    calls = {"import": 0, "log": []}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)
    monkeypatch.setattr(runtime.logger, "info", lambda msg, *args: calls["log"].append((msg, args)))

    mod, item = runtime.get_pystray()
    assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
    assert calls["import"] == 1
    assert ("pystray backend: %s", ("appindicator (auto-kde-wayland)",)) in calls["log"]
    assert install_calls == [True]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_falls_back_to_gtk_when_appindicator_import_fails_on_kde_wayland(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: True)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: None)
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: None)

    calls = {"import": 0}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        if calls["import"] == 1:
            assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
            raise RuntimeError("appindicator backend failed")
        assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)

    mod, item = runtime.get_pystray()
    assert calls["import"] == 2
    assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_explicit_appindicator_installs_log_filter(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "appindicator")
    install_calls = []
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(importlib, "import_module", lambda name: SimpleNamespace(MenuItem=object()))

    mod, item = runtime.get_pystray()

    assert install_calls == [True]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_prefers_appindicator_on_gnome(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: True)
    install_calls = []
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(
        runtime,
        "_install_gtk_scale_factor_log_filter",
        lambda: (_ for _ in ()).throw(AssertionError("installed gtk filter")),
    )
    calls = {"import": 0, "log": []}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)
    monkeypatch.setattr(runtime.logger, "info", lambda msg, *args: calls["log"].append((msg, args)))

    mod, item = runtime.get_pystray()
    assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
    assert calls["import"] == 1
    assert ("pystray backend: %s", ("appindicator (auto-gnome)",)) in calls["log"]
    assert install_calls == [True]
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_falls_back_to_gtk_when_appindicator_import_fails_on_gnome(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.setattr(runtime, "_is_kde_wayland_session", lambda: False)
    monkeypatch.setattr(runtime, "_is_gnome_session", lambda: True)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    monkeypatch.setattr(runtime, "_install_gtk_scale_factor_log_filter", lambda: None)
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: None)

    calls = {"import": 0}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        if calls["import"] == 1:
            assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
            raise RuntimeError("appindicator backend failed")
        assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
        return SimpleNamespace(MenuItem=object())

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)

    mod, item = runtime.get_pystray()
    assert calls["import"] == 2
    assert os.environ.get("PYSTRAY_BACKEND") == "gtk"
    assert item is getattr(mod, "MenuItem")


def test_acquire_single_instance_lock_uses_xdg_config_home(monkeypatch, tmp_path):
    class _FcntlStub:
        LOCK_EX = 1
        LOCK_NB = 2

        @staticmethod
        def flock(_fd, _flags):
            return None

    # Ensure the function takes the XDG path branch.
    monkeypatch.delenv("KEYRGB_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setitem(sys.modules, "fcntl", _FcntlStub)

    assert runtime.acquire_single_instance_lock() is True
    assert (tmp_path / "xdg" / "keyrgb" / "keyrgb.lock").exists()


def test_acquire_single_instance_lock_uses_home_fallback(monkeypatch, tmp_path):
    class _FcntlStub:
        LOCK_EX = 1
        LOCK_NB = 2

        @staticmethod
        def flock(_fd, _flags):
            return None

    monkeypatch.delenv("KEYRGB_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setitem(sys.modules, "fcntl", _FcntlStub)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    assert runtime.acquire_single_instance_lock() is True
    assert (tmp_path / "home" / ".config" / "keyrgb" / "keyrgb.lock").exists()
