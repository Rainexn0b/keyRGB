import importlib
import os
import sys
from pathlib import Path
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
    assert item is mod.MenuItem
    assert calls["import"] == 1
    assert any("(explicit)" in m for (m, _a) in calls["log"])


def test_get_pystray_explicit_backend_propagates_unexpected_import_bug(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "xorg")

    def _boom(_name: str):
        raise AssertionError("unexpected import bug")

    monkeypatch.setattr(importlib, "import_module", _boom)

    with pytest.raises(AssertionError, match="unexpected import bug"):
        runtime.get_pystray()


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
    assert item is mod.MenuItem


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
    assert item is mod.MenuItem


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
        assert item is mod.MenuItem
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
        assert item is mod.MenuItem
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
    assert item is mod.MenuItem


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
    assert item is mod.MenuItem


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
    assert item is mod.MenuItem


def test_get_pystray_explicit_appindicator_installs_log_filter(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "appindicator")
    install_calls = []
    monkeypatch.setattr(runtime, "_install_appindicator_deprecation_log_filter", lambda: install_calls.append(True))
    monkeypatch.setattr(importlib, "import_module", lambda name: SimpleNamespace(MenuItem=object()))

    mod, item = runtime.get_pystray()

    assert install_calls == [True]
    assert item is mod.MenuItem


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
    assert item is mod.MenuItem


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
    assert item is mod.MenuItem


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
