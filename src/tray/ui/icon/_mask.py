from __future__ import annotations

import importlib
import re
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw


_ICON_SIZE = (64, 64)
_ICON_INNER_SIZE = (48, 48)
_SVG_PATH_TOKEN_RE = re.compile(r"[MLZmlz]|-?\d+(?:\.\d+)?")
_CWD_PATH_ERRORS = (OSError,)


def candidate_tray_mask_paths() -> list[Path]:
    paths: list[Path] = []

    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "tray-mask.svg"
        if cand not in paths:
            paths.append(cand)

    try:
        paths.append(Path.cwd() / "assets" / "tray-mask.svg")
    except _CWD_PATH_ERRORS:
        pass

    for sys_cand in (
        Path("/usr/share/keyrgb/assets/tray-mask.svg"),
        Path("/usr/lib/keyrgb/assets/tray-mask.svg"),
        Path("/usr/local/share/keyrgb/assets/tray-mask.svg"),
        Path("/usr/local/lib/keyrgb/assets/tray-mask.svg"),
    ):
        if sys_cand not in paths:
            paths.append(sys_cand)

    return paths


def resampling_lanczos() -> int:
    return getattr(getattr(Image, "Resampling", None), "LANCZOS", getattr(Image, "LANCZOS", 1))


def center_alpha_mask(alpha: Image.Image) -> Image.Image:
    bbox = alpha.getbbox()
    if bbox is None:
        return Image.new("L", _ICON_SIZE, color=0)

    cropped = alpha.crop(bbox)
    src_w, src_h = cropped.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("L", _ICON_SIZE, color=0)

    scale = min(
        float(_ICON_INNER_SIZE[0]) / float(src_w),
        float(_ICON_INNER_SIZE[1]) / float(src_h),
    )
    dst_w = max(1, int(round(src_w * scale)))
    dst_h = max(1, int(round(src_h * scale)))
    inner = cropped.resize((dst_w, dst_h), resampling_lanczos())  # type: ignore[arg-type]

    out = Image.new("L", _ICON_SIZE, color=0)
    ox = (_ICON_SIZE[0] - dst_w) // 2
    oy = (_ICON_SIZE[1] - dst_h) // 2
    out.paste(inner, (ox, oy))
    return out


def parse_simple_svg_subpaths(path_data: str) -> list[list[tuple[float, float]]]:
    tokens = _SVG_PATH_TOKEN_RE.findall(path_data)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    command: str | None = None
    idx = 0

    while idx < len(tokens):
        token = tokens[idx]
        if token.isalpha():
            next_command = token
            idx += 1
            if next_command in {"Z", "z"}:
                if current:
                    subpaths.append(current)
                    current = []
                command = None
                continue
            if next_command in {"M", "m"} and current:
                subpaths.append(current)
                current = []
            command = next_command
            continue

        if command not in {"M", "L", "m", "l"} or (idx + 1) >= len(tokens):
            return []

        x = float(token)
        y = float(tokens[idx + 1])
        idx += 2

        if command in {"m", "l"}:
            x += cursor[0]
            y += cursor[1]

        cursor = (x, y)
        current.append(cursor)

        if command == "M":
            command = "L"
        elif command == "m":
            command = "l"

    if current:
        subpaths.append(current)

    return [subpath for subpath in subpaths if len(subpath) >= 3]


def render_simple_svg_mask_alpha_64(path: Path) -> Image.Image | None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    view_box = str(root.attrib.get("viewBox", "")).strip().split()
    if len(view_box) != 4:
        return None

    vb_x, vb_y, vb_w, vb_h = (float(part) for part in view_box)
    if vb_w <= 0 or vb_h <= 0:
        return None

    path_nodes = root.findall("{http://www.w3.org/2000/svg}path")
    if not path_nodes:
        return None

    render_size = (_ICON_INNER_SIZE[0] * 4, _ICON_INNER_SIZE[1] * 4)
    mask = Image.new("L", render_size, color=0)
    draw = ImageDraw.Draw(mask)
    scale_x = float(render_size[0]) / vb_w
    scale_y = float(render_size[1]) / vb_h

    drew_any = False
    for node in path_nodes:
        path_data = str(node.attrib.get("d", ""))
        for subpath in parse_simple_svg_subpaths(path_data):
            points = [((x - vb_x) * scale_x, (y - vb_y) * scale_y) for x, y in subpath]
            if len(points) >= 3:
                draw.polygon(points, fill=255)
                drew_any = True

    if not drew_any:
        return None

    return center_alpha_mask(mask)


def render_cairosvg_mask_alpha_64(path: Path) -> Image.Image:
    cairosvg = importlib.import_module("cairosvg")
    svg2png = getattr(cairosvg, "svg2png")
    png_bytes = svg2png(url=str(path), output_width=_ICON_INNER_SIZE[0], output_height=_ICON_INNER_SIZE[1])
    img = Image.open(BytesIO(png_bytes)).convert("RGBA")
    return center_alpha_mask(img.getchannel("A"))
