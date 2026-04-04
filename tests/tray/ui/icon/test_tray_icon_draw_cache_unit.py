from __future__ import annotations

from src.tray.ui.icon import _draw as icon_draw


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


def test_rainbow_gradient_uses_diagonal_axis() -> None:
    img = icon_draw._rainbow_gradient_64(16)

    same_diagonal_a = img.getpixel((16, 16))
    same_diagonal_b = img.getpixel((32, 0))
    different_diagonal = img.getpixel((16, 32))

    assert same_diagonal_a == same_diagonal_b
    assert same_diagonal_a != different_diagonal


def test_load_tray_mask_falls_back_to_simple_svg_when_cairosvg_rasterization_fails(monkeypatch, tmp_path) -> None:
    icon_draw._load_tray_mask_alpha_64.cache_clear()

    mask_path = tmp_path / "tray-mask.svg"
    mask_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    sentinel = icon_draw.Image.new("L", (64, 64), color=255)

    def raise_raster_error(_path) -> icon_draw.Image.Image:
        raise OSError("cairosvg failed")

    monkeypatch.setattr(icon_draw, "_candidate_tray_mask_paths", lambda: [mask_path])
    monkeypatch.setattr(icon_draw, "_render_cairosvg_mask_alpha_64", raise_raster_error)
    monkeypatch.setattr(icon_draw, "_render_simple_svg_mask_alpha_64", lambda _path: sentinel)

    assert icon_draw._load_tray_mask_alpha_64() is sentinel

    icon_draw._load_tray_mask_alpha_64.cache_clear()


def test_outline_color_for_theme_falls_back_when_theme_detection_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        icon_draw,
        "detect_system_prefers_dark",
        lambda: (_ for _ in ()).throw(OSError("theme detection failed")),
    )

    assert icon_draw._outline_color_for_theme() == (176, 176, 176)


def test_create_icon_mosaic_uses_default_color_when_representative_cell_is_malformed(monkeypatch) -> None:
    captured: dict[str, tuple[int, int, int]] = {}

    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    def fake_create_icon(color: tuple[int, int, int]):
        captured["color"] = tuple(color)
        return icon_draw.Image.new("RGBA", (1, 1), color=(*captured["color"], 255))

    monkeypatch.setattr(icon_draw, "create_icon", fake_create_icon)

    result = icon_draw.create_icon_mosaic(colors_flat=((255, 0),), rows=1, cols=2)

    assert result.size == (1, 1)
    assert captured["color"] == (255, 0, 128)
