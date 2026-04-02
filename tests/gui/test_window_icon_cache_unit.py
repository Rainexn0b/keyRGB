from __future__ import annotations

from io import BytesIO
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


def test_load_window_icon_image_rasterizes_svg_with_optional_cairosvg(tmp_path, monkeypatch) -> None:
    window_icon.clear_cached_window_icon_images()
    image_path = tmp_path / "icon.svg"
    image_path.write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'></svg>", encoding="utf-8")

    def fake_rasterize(path_str: str):
        assert path_str == str(image_path)
        out = BytesIO()
        Image.new("RGBA", (64, 64), color=(1, 2, 3, 255)).save(out, format="PNG")
        with Image.open(BytesIO(out.getvalue())) as image:
            return image.convert("RGBA")

    monkeypatch.setattr(window_icon, "_rasterize_svg_window_icon", fake_rasterize)

    image = window_icon.load_window_icon_image(image_path)

    assert image.size == (64, 64)
    assert image.getpixel((0, 0)) == (1, 2, 3, 255)

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


def test_apply_keyrgb_window_icon_falls_back_to_png_when_svg_cannot_be_rasterized(tmp_path, monkeypatch) -> None:
    window_icon.clear_cached_window_icon_images()
    svg_path = tmp_path / "icon.svg"
    png_path = tmp_path / "icon.png"
    svg_path.write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'></svg>", encoding="utf-8")
    _save_icon(png_path, (0, 0, 255, 255))

    created: list[object] = []

    def fake_photo(image):
        created.append(image)
        return {"image": image}

    monkeypatch.setattr(window_icon, "find_keyrgb_logo_path", lambda: svg_path)
    monkeypatch.setattr(window_icon, "_candidate_logo_paths", lambda: [svg_path, png_path])
    monkeypatch.setattr(
        window_icon,
        "_rasterize_svg_window_icon",
        lambda path_str: (_ for _ in ()).throw(ImportError(path_str)),
    )
    monkeypatch.setattr("PIL.ImageTk.PhotoImage", fake_photo)

    window = DummyWindow()
    window_icon.apply_keyrgb_window_icon(window)

    assert len(created) == 1
    assert created[0].getpixel((0, 0)) == (0, 0, 255, 255)
    assert len(window.iconphoto_calls) == 1

    window_icon.clear_cached_window_icon_images()


def test_find_keyrgb_logo_path_prefers_repo_asset_over_installed_icon(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_utils = repo_root / "src" / "gui" / "utils"
    repo_assets = repo_root / "assets"
    home_dir = tmp_path / "home"
    home_icon_dir = home_dir / ".local" / "share" / "icons"

    repo_utils.mkdir(parents=True)
    repo_assets.mkdir(parents=True)
    home_icon_dir.mkdir(parents=True)

    repo_icon = repo_assets / "logo-keyrgb.svg"
    installed_icon = home_icon_dir / "keyrgb.png"
    repo_icon.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    _save_icon(installed_icon, (255, 0, 0, 255))

    monkeypatch.setattr(window_icon, "__file__", str(repo_utils / "window_icon.py"))
    monkeypatch.setattr(window_icon.Path, "home", lambda: home_dir)

    assert window_icon.find_keyrgb_logo_path() == repo_icon
