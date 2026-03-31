from __future__ import annotations

import os
import types


def test_get_pystray_falls_back_to_xorg_on_broken_gi(monkeypatch):
    # Import locally to ensure we exercise module-level caching behavior.
    import src.tray.integrations.runtime as runtime

    # Reset cached module state for the test.
    monkeypatch.setattr(runtime, "_pystray_mod", None)
    monkeypatch.setattr(runtime, "_pystray_item", None)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: False)

    calls = {"n": 0}

    def fake_import_module(name: str):
        assert name == "pystray"
        calls["n"] += 1
        if calls["n"] == 1:
            # Simulate pystray failing to import because it picked the AppIndicator
            # backend and found a broken/non-PyGObject `gi`.
            raise AttributeError("module 'gi' has no attribute 'require_version'")
        m = types.SimpleNamespace(MenuItem=object())
        return m

    import importlib

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    mod, item = runtime.get_pystray()
    assert mod is not None
    assert item is not None
    assert os.environ.get("PYSTRAY_BACKEND") == "xorg"


def test_get_pystray_prefers_appindicator_when_gi_works(monkeypatch):
    import src.tray.integrations.runtime as runtime

    monkeypatch.setattr(runtime, "_pystray_mod", None)
    monkeypatch.setattr(runtime, "_pystray_item", None)
    monkeypatch.delenv("PYSTRAY_BACKEND", raising=False)

    # Pretend PyGObject is usable.
    monkeypatch.setattr(runtime, "_gi_is_working", lambda: True)

    calls = {"n": 0}

    def fake_import_module(name: str):
        assert name == "pystray"
        calls["n"] += 1

        # First attempt should be AppIndicator.
        if calls["n"] == 1:
            assert os.environ.get("PYSTRAY_BACKEND") == "appindicator"
            raise ImportError("AppIndicator not available")

        # Second attempt should fall back to Xorg.
        assert os.environ.get("PYSTRAY_BACKEND") == "xorg"
        return types.SimpleNamespace(MenuItem=object())

    import importlib

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    mod, item = runtime.get_pystray()
    assert mod is not None
    assert item is not None
