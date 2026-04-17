from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.editor_support.layout as editor_layout


def test_normalize_layout_legend_pack_uses_layout_module_loader(monkeypatch) -> None:
    calls: list[str] = []

    def fake_load_layout_legend_pack(pack_id: str) -> dict[str, str]:
        calls.append(pack_id)
        return {"layout_id": "ansi"}

    monkeypatch.setattr(editor_layout, "load_layout_legend_pack", fake_load_layout_legend_pack)

    assert editor_layout.normalize_layout_legend_pack("ansi", "compact") == "compact"
    assert editor_layout.normalize_layout_legend_pack("iso", "compact") == "auto"
    assert calls == ["compact", "compact"]


def test_load_layout_tweaks_uses_default_profiles_module(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_load_layout_global(profile_name: str, *, physical_layout: str) -> dict[str, float]:
        calls.append((profile_name, physical_layout))
        return {"offset_x": 1.5}

    monkeypatch.setattr(editor_layout.profiles, "load_layout_global", fake_load_layout_global)

    app = SimpleNamespace(profile_name="demo-profile", _physical_layout="iso")

    assert editor_layout.load_layout_tweaks(app) == {"offset_x": 1.5}
    assert calls == [("demo-profile", "iso")]