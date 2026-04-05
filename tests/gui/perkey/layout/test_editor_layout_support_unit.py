from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.editor_support.layout as editor_layout


def test_load_layout_tweaks_uses_default_profiles_module(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_load_layout_global(profile_name: str, *, physical_layout: str) -> dict[str, float]:
        calls.append((profile_name, physical_layout))
        return {"offset_x": 1.5}

    monkeypatch.setattr(editor_layout.profiles, "load_layout_global", fake_load_layout_global)

    app = SimpleNamespace(profile_name="demo-profile", _physical_layout="iso")

    assert editor_layout.load_layout_tweaks(app) == {"offset_x": 1.5}
    assert calls == [("demo-profile", "iso")]