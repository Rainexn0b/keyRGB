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
