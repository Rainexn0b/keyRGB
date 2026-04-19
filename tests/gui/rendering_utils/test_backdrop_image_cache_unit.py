from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from PIL import Image

from src.gui.utils import backdrop_image_cache
from src.gui.utils.backdrop_image_cache import clear_cached_backdrop_images, load_cached_backdrop_image
from src.gui.utils.profile_backdrop_storage import load_backdrop_image


def _save_rgba(path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (4, 4), color=color).save(path)


def test_backdrop_loader_and_cache_share_cached_rgba_image(tmp_path, monkeypatch) -> None:
    clear_cached_backdrop_images()
    image_path = tmp_path / "deck.png"
    _save_rgba(image_path, (255, 0, 0, 255))

    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=image_path),
    )
    monkeypatch.setattr(backdrop_image_cache.profiles, "load_backdrop_mode", lambda _name: "custom")

    first = load_backdrop_image("profile-1")
    second = load_cached_backdrop_image(candidates=(image_path,))

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
    monkeypatch.setattr(backdrop_image_cache.profiles, "load_backdrop_mode", lambda _name: "custom")

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


def test_backdrop_loader_returns_none_when_mode_is_none(tmp_path, monkeypatch) -> None:
    clear_cached_backdrop_images()
    image_path = tmp_path / "deck.png"
    _save_rgba(image_path, (255, 0, 0, 255))

    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=image_path),
    )
    monkeypatch.setattr(backdrop_image_cache.profiles, "load_backdrop_mode", lambda _name: "none")

    assert load_backdrop_image("profile-1") is None

    clear_cached_backdrop_images()


def test_backdrop_loader_returns_none_when_custom_mode_has_no_saved_image(tmp_path, monkeypatch) -> None:
    clear_cached_backdrop_images()
    missing_image_path = tmp_path / "missing-deck.png"

    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=missing_image_path),
    )
    monkeypatch.setattr(backdrop_image_cache.profiles, "load_backdrop_mode", lambda _name: "custom")

    assert load_backdrop_image("profile-1") is None

    clear_cached_backdrop_images()


def test_backdrop_image_candidates_keeps_repo_fallback_when_profile_lookup_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: (_ for _ in ()).throw(RuntimeError("broken profile lookup")),
    )

    candidates = backdrop_image_cache.backdrop_image_candidates(profile_name="profile-1")

    assert len(candidates) == 1
    assert candidates[0].as_posix().endswith("/assets/y15-pro-deck.png")


def test_backdrop_image_candidates_propagates_unexpected_profile_lookup_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: (_ for _ in ()).throw(AssertionError("broken profile lookup")),
    )

    with pytest.raises(AssertionError):
        backdrop_image_cache.backdrop_image_candidates(profile_name="profile-1")


def test_backdrop_image_candidates_ignores_cwd_fallback_oserror(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "deck.png"
    monkeypatch.setattr(
        backdrop_image_cache.profiles,
        "paths_for",
        lambda _name: SimpleNamespace(backdrop_image=image_path),
    )
    monkeypatch.setattr(backdrop_image_cache.Path, "cwd", lambda: (_ for _ in ()).throw(OSError("cwd unavailable")))

    assert backdrop_image_cache.backdrop_image_candidates(profile_name="profile-1", include_cwd_fallback=True) == (
        image_path,
        backdrop_image_cache.Path(__file__).resolve().parents[3] / "assets" / "y15-pro-deck.png",
    )


def test_backdrop_image_candidates_uses_structural_repo_root_for_packaged_layout(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "gui" / "utils" / "backdrop_image_cache.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    monkeypatch.setattr(backdrop_image_cache, "__file__", str(anchor))

    candidates = backdrop_image_cache.backdrop_image_candidates(profile_name=None)

    assert candidates == (runtime_root / "assets" / "y15-pro-deck.png",)
