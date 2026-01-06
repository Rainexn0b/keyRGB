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


def test_force_pystray_backend_xorg_only_sets_if_missing(monkeypatch):
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    runtime._force_pystray_backend_xorg()
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"

    monkeypatch.setenv("PYSTRAY_BACKEND", "appindicator")
    runtime._force_pystray_backend_xorg()
    assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"


def test_set_pystray_backend_xorg_for_retry_overrides(monkeypatch):
    monkeypatch.setenv("PYSTRAY_BACKEND", "appindicator")
    runtime._set_pystray_backend_xorg_for_retry()
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"


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
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: (_ for _ in ()).throw(AssertionError("probed gi")))

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


def test_get_pystray_prefers_appindicator_when_gi_works(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
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
    assert any("appindicator (auto)" in m for (m, _a) in calls["log"])
    assert item is getattr(mod, "MenuItem")


def test_get_pystray_falls_back_to_xorg_when_appindicator_import_fails(monkeypatch):
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)

    previous = sys.modules.get("pystray")
    sentinel_partial = object()
    sys.modules["pystray"] = sentinel_partial

    calls = {"import": 0}

    def _fake_import_module(name: str):
        assert name == "pystray"
        calls["import"] += 1
        if calls["import"] == 1:
            raise RuntimeError("appindicator backend failed")
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


