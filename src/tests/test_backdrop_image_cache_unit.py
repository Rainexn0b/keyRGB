from __future__ import annotations

import os
from types import SimpleNamespace

from PIL import Image

from src.gui.reference.deck_image import load_reference_deck_image
from src.gui.utils import backdrop_image_cache
from src.gui.utils.backdrop_image_cache import clear_cached_backdrop_images
from src.gui.utils.profile_backdrop_storage import load_backdrop_image


def _save_rgba(path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (4, 4), color=color).save(path)


def test_backdrop_loaders_share_cached_rgba_image(tmp_path, monkeypatch) -> None:
    clear_cached_backdrop_images()
    image_path = tmp_path / "deck.png"
    _save_rgba(image_path, (255, 0, 0, 255))

    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=image_path),
    )

    first = load_backdrop_image("profile-1")
    second = load_reference_deck_image(profile_name="profile-1")

    assert first is not None
    assert first is second
    assert first.mode == "RGBA"

    clear_cached_backdrop_images()


def test_backdrop_cache_invalidates_when_file_changes(tmp_path, monkeypatch) -> None:
    clear_cached_backdrop_images()
    image_path = tmp_path / "deck.png"
    _save_rgba(image_path, (255, 0, 0, 255))

    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=image_path),
    )

    first = load_backdrop_image("profile-1")
    assert first is not None
    assert first.getpixel((0, 0)) == (255, 0, 0, 255)

    _save_rgba(image_path, (0, 0, 255, 255))
    stat = image_path.stat()
    os.utime(image_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    second = load_backdrop_image("profile-1")

    assert second is not None
    assert second is not first
    assert second.getpixel((0, 0)) == (0, 0, 255, 255)

    clear_cached_backdrop_images()
