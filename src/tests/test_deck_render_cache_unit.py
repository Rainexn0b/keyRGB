from __future__ import annotations

from PIL import Image

from src.gui.utils.deck_render_cache import DeckRenderCache


def test_deck_render_cache_reuses_photo_for_same_inputs() -> None:
    cache: DeckRenderCache[str] = DeckRenderCache()
    deck = Image.new("RGBA", (12, 12), color=(10, 20, 30, 255))
    created: list[tuple[int, int]] = []

    def photo_factory(image: Image.Image) -> str:
        created.append(image.size)
        return f"photo-{len(created)}"

    first = cache.get_or_create(
        deck_image=deck,
        draw_size=(8, 6),
        transparency_pct=0.0,
        photo_factory=photo_factory,
    )
    second = cache.get_or_create(
        deck_image=deck,
        draw_size=(8, 6),
        transparency_pct=0.0,
        photo_factory=photo_factory,
    )

    assert first == "photo-1"
    assert second == "photo-1"
    assert created == [(8, 6)]


def test_deck_render_cache_rebuilds_when_transparency_changes() -> None:
    cache: DeckRenderCache[Image.Image] = DeckRenderCache()
    deck = Image.new("RGBA", (10, 10), color=(50, 60, 70, 255))

    opaque = cache.get_or_create(
        deck_image=deck,
        draw_size=(4, 4),
        transparency_pct=0.0,
        photo_factory=lambda image: image.copy(),
    )
    half = cache.get_or_create(
        deck_image=deck,
        draw_size=(4, 4),
        transparency_pct=50.0,
        photo_factory=lambda image: image.copy(),
    )

    assert opaque is not None
    assert half is not None
    assert opaque.getchannel("A").getextrema() == (255, 255)
    assert half.getchannel("A").getextrema() == (127, 127)


def test_deck_render_cache_rebuilds_for_new_deck_image() -> None:
    cache: DeckRenderCache[str] = DeckRenderCache()
    first_deck = Image.new("RGBA", (8, 8), color=(255, 0, 0, 255))
    second_deck = Image.new("RGBA", (8, 8), color=(0, 255, 0, 255))
    created: list[tuple[int, int, int, int]] = []

    def photo_factory(image: Image.Image) -> str:
        created.append(image.getpixel((0, 0)))
        return f"photo-{len(created)}"

    first = cache.get_or_create(
        deck_image=first_deck,
        draw_size=(5, 5),
        transparency_pct=0.0,
        photo_factory=photo_factory,
    )
    second = cache.get_or_create(
        deck_image=second_deck,
        draw_size=(5, 5),
        transparency_pct=0.0,
        photo_factory=photo_factory,
    )

    assert first == "photo-1"
    assert second == "photo-2"
    assert created == [(255, 0, 0, 255), (0, 255, 0, 255)]