from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.tray.ui import icon_draw


def test_create_icon_reuses_cached_image_for_same_color(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon((10, 20, 30))
    second = icon_draw.create_icon((10, 20, 30))

    assert first is second

    icon_draw.clear_cached_solid_icons()


def test_create_icon_separates_cache_entries_by_color(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
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
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)
    second = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)

    assert first is second

    icon_draw.clear_cached_rainbow_icons()


def test_create_icon_rainbow_separates_cache_entries_by_phase(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.10)
    second = icon_draw.create_icon_rainbow(scale=0.5, phase=0.30)

    assert first is not second

    icon_draw.clear_cached_rainbow_icons()


def test_create_icon_rainbow_separates_cache_entries_by_scale(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    first = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)
    second = icon_draw.create_icon_rainbow(scale=0.8, phase=0.25)

    assert first is not second

    icon_draw.clear_cached_rainbow_icons()


def test_tray_k_mask_expands_cutout_into_bolder_glyph(monkeypatch) -> None:
    icon_draw._tray_k_mask.cache_clear()

    loaded = Image.new("L", icon_draw._ICON_SIZE, color=0)
    for x in range(6, 58):
        for y in range(4, 60):
            loaded.putpixel((x, y), 255)

    monkeypatch.setattr(icon_draw, "_load_tray_mask_alpha_64", lambda: loaded)

    mask = icon_draw._tray_k_mask()

    assert mask is not None
    bbox = mask.getbbox()
    assert bbox is not None
    assert bbox == (6, 4, 58, 60)

    icon_draw._tray_k_mask.cache_clear()


def test_create_icon_renders_k_only_mark_without_outer_squirkle(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()

    k_mask = Image.new("L", icon_draw._ICON_SIZE, color=0)
    for x in range(8, 56):
        for y in range(8, 56):
            k_mask.putpixel((x, y), 255)

    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: k_mask)

    image = icon_draw.create_icon((10, 20, 30))

    assert image.getpixel((4, 4))[3] == 0
    assert image.getpixel((10, 10))[3] > 0
    assert image.getpixel((21, 21))[3] > 0
    assert image.getpixel((32, 32))[3] == 255

    icon_draw.clear_cached_solid_icons()


def test_simple_svg_mask_renderer_loads_real_asset() -> None:
    asset = Path(__file__).resolve().parents[2] / "assets" / "tray-mask.svg"

    mask = icon_draw._render_simple_svg_mask_alpha_64(asset)

    assert mask is not None
    assert mask.size == icon_draw._ICON_SIZE
    bbox = mask.getbbox()
    assert bbox is not None
    assert bbox == (8, 8, 56, 56)
