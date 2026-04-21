from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from src.tray.ui.icon import _mask as icon_mask


def test_candidate_tray_mask_paths_includes_deduped_parent_candidates_and_cwd(monkeypatch, tmp_path) -> None:
    fake_file = tmp_path / "pkg" / "tray" / "_mask.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(icon_mask, "__file__", str(fake_file))
    monkeypatch.setattr(icon_mask.Path, "cwd", staticmethod(lambda: tmp_path))

    paths = icon_mask.candidate_tray_mask_paths()
    expected = tmp_path / "assets" / "tray-mask.svg"

    assert expected in paths

    start = Path(str(fake_file)).resolve()
    expected_parent_candidates = []
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "tray-mask.svg"
        if cand not in expected_parent_candidates:
            expected_parent_candidates.append(cand)

    parent_candidates = paths[: len(expected_parent_candidates)]
    assert parent_candidates == expected_parent_candidates


def test_candidate_tray_mask_paths_swallows_cwd_oserror_and_dedupes_usr_candidates(monkeypatch) -> None:
    monkeypatch.setattr(icon_mask, "__file__", "/usr/share/keyrgb/src/tray/ui/icon/_mask.py")

    def _raise_oserror() -> Path:
        raise OSError("cwd unavailable")

    monkeypatch.setattr(icon_mask.Path, "cwd", staticmethod(_raise_oserror))

    paths = icon_mask.candidate_tray_mask_paths()

    usr_share = Path("/usr/share/keyrgb/assets/tray-mask.svg")
    usr_lib = Path("/usr/lib/keyrgb/assets/tray-mask.svg")
    usr_local_share = Path("/usr/local/share/keyrgb/assets/tray-mask.svg")
    usr_local_lib = Path("/usr/local/lib/keyrgb/assets/tray-mask.svg")

    assert paths.count(usr_share) == 1
    assert paths.count(usr_lib) == 1
    assert paths.count(usr_local_share) == 1
    assert paths.count(usr_local_lib) == 1


def test_resampling_lanczos_prefers_image_resampling_attr(monkeypatch) -> None:
    fake_image = SimpleNamespace(
        Resampling=SimpleNamespace(LANCZOS=777),
        LANCZOS=555,
    )
    monkeypatch.setattr(icon_mask, "Image", fake_image)

    assert icon_mask.resampling_lanczos() == 777


def test_resampling_lanczos_falls_back_to_image_lanczos_or_default(monkeypatch) -> None:
    monkeypatch.setattr(icon_mask, "Image", SimpleNamespace(LANCZOS=333))
    assert icon_mask.resampling_lanczos() == 333

    monkeypatch.setattr(icon_mask, "Image", SimpleNamespace())
    assert icon_mask.resampling_lanczos() == 1


def test_center_alpha_mask_returns_empty_icon_for_none_bbox() -> None:
    alpha = Image.new("L", (64, 64), color=0)

    out = icon_mask.center_alpha_mask(alpha)

    assert out.mode == "L"
    assert out.size == (64, 64)
    assert out.getbbox() is None


def test_center_alpha_mask_defensive_zero_source_size_returns_empty_icon() -> None:
    class _FakeCrop:
        size = (0, 12)

    class _FakeAlpha:
        @staticmethod
        def getbbox():
            return (1, 1, 5, 5)

        @staticmethod
        def crop(_bbox):
            return _FakeCrop()

    out = icon_mask.center_alpha_mask(_FakeAlpha())

    assert out.mode == "L"
    assert out.size == (64, 64)
    assert out.getbbox() is None


def test_center_alpha_mask_centers_non_empty_shape() -> None:
    alpha = Image.new("L", (100, 40), color=0)
    alpha.paste(255, (10, 5, 90, 35))

    out = icon_mask.center_alpha_mask(alpha)
    bbox = out.getbbox()

    assert out.mode == "L"
    assert out.size == (64, 64)
    assert bbox is not None
    left, top, right, bottom = bbox
    assert left > 0
    assert top > 0
    assert right < 64
    assert bottom < 64


def test_parse_simple_svg_subpaths_parses_absolute_m_l_z_path() -> None:
    out = icon_mask.parse_simple_svg_subpaths("M 0 0 L 10 0 L 10 10 Z")

    assert out == [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]]


def test_parse_simple_svg_subpaths_parses_relative_m_l_path() -> None:
    out = icon_mask.parse_simple_svg_subpaths("m 1 1 l 2 0 l 0 2 z")

    assert out == [[(1.0, 1.0), (3.0, 1.0), (3.0, 3.0)]]


def test_parse_simple_svg_subpaths_returns_empty_for_invalid_command_stream() -> None:
    assert icon_mask.parse_simple_svg_subpaths("Q 0 0 1 1") == []


def test_parse_simple_svg_subpaths_appends_trailing_current_path_without_z() -> None:
    out = icon_mask.parse_simple_svg_subpaths("M 0 0 L 5 0 L 5 5")

    assert out == [[(0.0, 0.0), (5.0, 0.0), (5.0, 5.0)]]


def test_render_simple_svg_mask_alpha_64_returns_none_for_invalid_viewbox_len(tmp_path) -> None:
    path = tmp_path / "mask.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24"/>', encoding="utf-8")

    assert icon_mask.render_simple_svg_mask_alpha_64(path) is None


def test_render_simple_svg_mask_alpha_64_returns_none_for_non_positive_viewbox_dims(tmp_path) -> None:
    path = tmp_path / "mask.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 0 24"/>', encoding="utf-8")

    assert icon_mask.render_simple_svg_mask_alpha_64(path) is None


def test_render_simple_svg_mask_alpha_64_returns_none_when_no_path_nodes(tmp_path) -> None:
    path = tmp_path / "mask.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"/>', encoding="utf-8")

    assert icon_mask.render_simple_svg_mask_alpha_64(path) is None


def test_render_simple_svg_mask_alpha_64_returns_none_when_no_drawable_polygons(tmp_path) -> None:
    path = tmp_path / "mask.svg"
    path.write_text(
        (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M 0 0 L 1 1"/>'
            "</svg>"
        ),
        encoding="utf-8",
    )

    assert icon_mask.render_simple_svg_mask_alpha_64(path) is None


def test_render_simple_svg_mask_alpha_64_success_returns_centered_mask(tmp_path) -> None:
    path = tmp_path / "mask.svg"
    path.write_text(
        (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M 4 4 L 20 4 L 20 20 L 4 20 Z"/>'
            "</svg>"
        ),
        encoding="utf-8",
    )

    out = icon_mask.render_simple_svg_mask_alpha_64(path)

    assert out is not None
    assert out.mode == "L"
    assert out.size == (64, 64)
    assert out.getbbox() is not None


def test_render_cairosvg_mask_alpha_64_returns_centered_alpha_mask(monkeypatch, tmp_path) -> None:
    png = Image.new("RGBA", (3, 3), color=(0, 0, 0, 0))
    png.putpixel((1, 1), (255, 255, 255, 255))

    from io import BytesIO

    payload = BytesIO()
    png.save(payload, format="PNG")
    png_bytes = payload.getvalue()
    calls: dict[str, object] = {}

    def _svg2png(*, url: str, output_width: int, output_height: int) -> bytes:
        calls["url"] = url
        calls["output_width"] = output_width
        calls["output_height"] = output_height
        return png_bytes

    monkeypatch.setattr(icon_mask.importlib, "import_module", lambda name: SimpleNamespace(svg2png=_svg2png) if name == "cairosvg" else None)

    svg_path = tmp_path / "mask.svg"
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    out = icon_mask.render_cairosvg_mask_alpha_64(svg_path)

    assert calls == {
        "url": str(svg_path),
        "output_width": 48,
        "output_height": 48,
    }
    assert out.mode == "L"
    assert out.size == (64, 64)
    assert out.getbbox() is not None