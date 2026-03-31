from __future__ import annotations

from src.tray.ui import icon_draw


def test_create_icon_reuses_cached_image_for_same_color(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon((10, 20, 30))
    second = icon_draw.create_icon((10, 20, 30))

    assert first is second

    icon_draw.clear_cached_solid_icons()


def test_create_icon_separates_cache_entries_by_color(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon((10, 20, 30))
    second = icon_draw.create_icon((30, 20, 10))

    assert first is not second

    icon_draw.clear_cached_solid_icons()


def test_create_icon_separates_cache_entries_by_outline_theme(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    dark_pref = icon_draw.create_icon((10, 20, 30))

    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (79, 79, 79))
    light_pref = icon_draw.create_icon((10, 20, 30))

    assert light_pref is not dark_pref

    icon_draw.clear_cached_solid_icons()


def test_create_icon_rainbow_reuses_cached_image_for_same_phase_and_scale(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)
    second = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)

    assert first is second

    icon_draw.clear_cached_rainbow_icons()


def test_create_icon_rainbow_separates_cache_entries_by_phase(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.10)
    second = icon_draw.create_icon_rainbow(scale=0.5, phase=0.30)

    assert first is not second

    icon_draw.clear_cached_rainbow_icons()


def test_create_icon_rainbow_separates_cache_entries_by_scale(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_outline_color_for_theme", lambda: (176, 176, 176))
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)
    second = icon_draw.create_icon_rainbow(scale=0.8, phase=0.25)

    assert first is not second

    icon_draw.clear_cached_rainbow_icons()
