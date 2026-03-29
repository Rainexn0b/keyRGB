from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from PIL import Image

PhotoT = TypeVar("PhotoT")


def _transparency_key(transparency_pct: float) -> int:
    try:
        value = float(transparency_pct)
    except Exception:
        value = 0.0
    value = max(0.0, min(100.0, value))
    return int(round(value * 1000.0))


def _apply_transparency(rendered: Image.Image, transparency_pct: float) -> Image.Image:
    if transparency_pct <= 0.0:
        return rendered

    alpha_mul = max(0.0, min(1.0, (100.0 - transparency_pct) / 100.0))
    alpha = rendered.getchannel("A")
    alpha = alpha.point(lambda px: int(px * alpha_mul))
    rendered.putalpha(alpha)
    return rendered


@dataclass
class DeckRenderCache(Generic[PhotoT]):
    key: tuple[int, int, int, int] | None = None
    photo: PhotoT | None = None

    def clear(self) -> None:
        self.key = None
        self.photo = None

    def get_or_create(
        self,
        *,
        deck_image: Image.Image | None,
        draw_size: tuple[int, int],
        transparency_pct: float,
        photo_factory: Callable[[Image.Image], PhotoT],
    ) -> PhotoT | None:
        if deck_image is None:
            self.clear()
            return None

        draw_w = max(1, int(draw_size[0]))
        draw_h = max(1, int(draw_size[1]))
        cache_key = (id(deck_image), draw_w, draw_h, _transparency_key(transparency_pct))
        if cache_key == self.key and self.photo is not None:
            return self.photo

        rendered = deck_image.resize((draw_w, draw_h), Image.Resampling.LANCZOS)
        rendered = _apply_transparency(rendered, transparency_pct)
        self.photo = photo_factory(rendered)
        self.key = cache_key
        return self.photo
