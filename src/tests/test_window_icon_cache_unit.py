from __future__ import annotations

import os

from PIL import Image

from src.gui.utils import window_icon


class DummyWindow:
    def __init__(self) -> None:
        self.iconphoto_calls: list[tuple[bool, object]] = []

    def iconphoto(self, default: bool, photo: object) -> None:
        self.iconphoto_calls.append((default, photo))


def _save_icon(path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (16, 16), color=color).save(path)


def test_load_window_icon_image_reuses_cached_resized_image(tmp_path) -> None:
    window_icon.clear_cached_window_icon_images()
    image_path = tmp_path / "icon.png"
    _save_icon(image_path, (255, 0, 0, 255))

    first = window_icon.load_window_icon_image(image_path)
    second = window_icon.load_window_icon_image(image_path)

    assert first is second
    assert first.size == (64, 64)

    window_icon.clear_cached_window_icon_images()


def test_load_window_icon_image_invalidates_when_file_changes(tmp_path) -> None:
    window_icon.clear_cached_window_icon_images()
    image_path = tmp_path / "icon.png"
    _save_icon(image_path, (255, 0, 0, 255))

    first = window_icon.load_window_icon_image(image_path)
    assert first.getpixel((0, 0)) == (255, 0, 0, 255)

    _save_icon(image_path, (0, 0, 255, 255))
    stat = image_path.stat()
    os.utime(image_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    second = window_icon.load_window_icon_image(image_path)

    assert second is not first
    assert second.getpixel((0, 0)) == (0, 0, 255, 255)

    window_icon.clear_cached_window_icon_images()


def test_apply_keyrgb_window_icon_uses_cached_source_image(tmp_path, monkeypatch) -> None:
    window_icon.clear_cached_window_icon_images()
    image_path = tmp_path / "icon.png"
    _save_icon(image_path, (255, 0, 0, 255))

    opens = {"count": 0}

    original_open = Image.open

    def counting_open(*args, **kwargs):
        opens["count"] += 1
        return original_open(*args, **kwargs)

    created: list[object] = []

    def fake_photo(image):
        created.append(image)
        return {"image": image}

    monkeypatch.setattr(window_icon, "find_keyrgb_logo_path", lambda: image_path)
    monkeypatch.setattr("PIL.Image.open", counting_open)
    monkeypatch.setattr("PIL.ImageTk.PhotoImage", fake_photo)

    first_window = DummyWindow()
    second_window = DummyWindow()

    window_icon.apply_keyrgb_window_icon(first_window)
    window_icon.apply_keyrgb_window_icon(second_window)

    assert opens["count"] == 1
    assert len(created) == 2
    assert created[0] is created[1]
    assert len(first_window.iconphoto_calls) == 1
    assert len(second_window.iconphoto_calls) == 1

    window_icon.clear_cached_window_icon_images()
