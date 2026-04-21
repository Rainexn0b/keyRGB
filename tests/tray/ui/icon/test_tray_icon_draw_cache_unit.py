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


def test_outline_color_for_theme_inverts_when_light_theme_is_preferred(monkeypatch) -> None:
    monkeypatch.setattr(icon_draw, "detect_system_prefers_dark", lambda: False)

    assert icon_draw._outline_color_for_theme() == (79, 79, 79)


def test_scale_cache_key_clamps_to_u10_range() -> None:
    assert icon_draw._scale_cache_key(-1.5) == 0
    assert icon_draw._scale_cache_key(1.5) == 1000
    assert icon_draw._scale_cache_key(0.1236) == 124


def test_clamp_u8_and_scale_rgb_enforce_boundaries() -> None:
    assert icon_draw._clamp_u8(-4.2) == 0
    assert icon_draw._clamp_u8(255.6) == 255
    assert icon_draw._clamp_u8(127.4) == 127

    assert icon_draw._scale_rgb((300, -10, 127), 0.5) == (150, 0, 64)
    assert icon_draw._scale_rgb((1, 2, 3), -1.0) == (0, 0, 0)
    assert icon_draw._scale_rgb((1, 2, 3), 2.0) == (1, 2, 3)


def test_create_icon_uses_mask_when_available(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: icon_draw.Image.new("L", (64, 64), color=255))

    img = icon_draw.create_icon((7, 8, 9))

    assert img.getpixel((0, 0)) == (7, 8, 9, 255)


def test_create_icon_fallback_draws_placeholder_when_mask_missing(monkeypatch) -> None:
    icon_draw.clear_cached_solid_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)

    img = icon_draw.create_icon((11, 22, 33))

    assert img.getpixel((0, 0)) == (0, 0, 0, 0)
    assert img.getpixel((8, 20)) == (11, 22, 33, 255)


def test_create_icon_rainbow_uses_masked_gradient_path(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: icon_draw.Image.new("L", (64, 64), color=255))
    monkeypatch.setattr(icon_draw, "_rainbow_gradient_64", lambda _phase_q: icon_draw.Image.new("RGBA", (64, 64), color=(10, 20, 30, 255)))

    def _unexpected_create_icon(_color):
        raise AssertionError("rainbow masked path should not call create_icon fallback")

    monkeypatch.setattr(icon_draw, "create_icon", _unexpected_create_icon)

    img = icon_draw.create_icon_rainbow(scale=0.5, phase=0.25)

    assert img.getpixel((10, 10)) == (5, 10, 15, 255)


def test_create_icon_rainbow_falls_back_to_solid_when_mask_missing(monkeypatch) -> None:
    icon_draw.clear_cached_rainbow_icons()
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: None)
    captured: dict[str, tuple[int, int, int]] = {}

    def fake_create_icon(color: tuple[int, int, int]):
        captured["color"] = tuple(color)
        return icon_draw.Image.new("RGBA", (1, 1), color=(*captured["color"], 255))

    monkeypatch.setattr(icon_draw, "create_icon", fake_create_icon)

    out = icon_draw.create_icon_rainbow(scale=0.5, phase=0.0)

    assert out.size == (1, 1)
    assert captured["color"] == (128, 0, 0)


def test_clear_cached_solid_icons_clears_callable_cache_entries(monkeypatch) -> None:
    calls = {"solid": 0, "mask_loader": 0}

    class _SolidCache:
        @staticmethod
        def cache_clear() -> None:
            calls["solid"] += 1

    class _MaskLoader:
        @staticmethod
        def cache_clear() -> None:
            calls["mask_loader"] += 1

    class _MaskAccessor:
        cache_clear = "not-callable"

    monkeypatch.setattr(icon_draw, "_create_cached_solid_icon", _SolidCache)
    monkeypatch.setattr(icon_draw, "_load_tray_mask_alpha_64", _MaskLoader)
    monkeypatch.setattr(icon_draw, "_tray_k_mask", _MaskAccessor)

    icon_draw.clear_cached_solid_icons()

    assert calls == {"solid": 1, "mask_loader": 1}


def test_clear_cached_rainbow_icons_clears_callable_cache_entries(monkeypatch) -> None:
    calls = {"rainbow": 0, "mask_accessor": 0}

    class _RainbowCache:
        @staticmethod
        def cache_clear() -> None:
            calls["rainbow"] += 1

    class _MaskLoader:
        cache_clear = "not-callable"

    class _MaskAccessor:
        @staticmethod
        def cache_clear() -> None:
            calls["mask_accessor"] += 1

    monkeypatch.setattr(icon_draw, "_create_cached_rainbow_icon", _RainbowCache)
    monkeypatch.setattr(icon_draw, "_load_tray_mask_alpha_64", _MaskLoader)
    monkeypatch.setattr(icon_draw, "_tray_k_mask", _MaskAccessor)

    icon_draw.clear_cached_rainbow_icons()

    assert calls == {"rainbow": 1, "mask_accessor": 1}


def test_create_icon_mosaic_masked_mismatch_falls_back_to_representative_color(monkeypatch) -> None:
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: icon_draw.Image.new("L", (64, 64), color=255))
    captured: dict[str, tuple[int, int, int]] = {}

    def fake_create_icon(color: tuple[int, int, int]):
        captured["color"] = tuple(color)
        return icon_draw.Image.new("RGBA", (1, 1), color=(*captured["color"], 255))

    monkeypatch.setattr(icon_draw, "create_icon", fake_create_icon)

    result = icon_draw.create_icon_mosaic(
        colors_flat=((10, 20, 30),),
        rows=2,
        cols=2,
        scale=0.5,
    )

    assert result.size == (1, 1)
    assert captured["color"] == (5, 10, 15)


def test_create_icon_mosaic_draws_expected_grid_when_shape_matches(monkeypatch) -> None:
    monkeypatch.setattr(icon_draw, "_tray_k_mask", lambda: icon_draw.Image.new("L", (64, 64), color=255))

    img = icon_draw.create_icon_mosaic(
        colors_flat=((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)),
        rows=2,
        cols=2,
        scale=1.0,
    )

    assert img.getpixel((16, 16)) == (255, 0, 0, 255)
    assert img.getpixel((48, 16)) == (0, 255, 0, 255)
    assert img.getpixel((16, 48)) == (0, 0, 255, 255)
    assert img.getpixel((48, 48)) == (255, 255, 0, 255)


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
