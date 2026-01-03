from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef


@dataclass(frozen=True)
class CanvasTransform:
    """Affine transform from base-image coordinates to canvas coordinates."""

    x0: float
    y0: float
    sx: float
    sy: float

    def to_canvas(self, rect: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x, y, w, h = rect
        x1 = self.x0 + x * self.sx
        y1 = self.y0 + y * self.sy
        x2 = self.x0 + (x + w) * self.sx
        y2 = self.y0 + (y + h) * self.sy
        return x1, y1, x2, y2


def calc_centered_transform(
    *,
    canvas_w: int,
    canvas_h: int,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> CanvasTransform:
    """Scale an image to fit inside canvas, centered, preserving aspect ratio."""

    cw = max(1, int(canvas_w))
    ch = max(1, int(canvas_h))
    iw, ih = image_size

    s = min(cw / iw, ch / ih)
    draw_w = iw * s
    draw_h = ih * s
    x0 = (cw - draw_w) / 2
    y0 = (ch - draw_h) / 2
    return CanvasTransform(x0=x0, y0=y0, sx=s, sy=s)


def transform_from_drawn_bbox(
    *,
    x0: int,
    y0: int,
    draw_w: int,
    draw_h: int,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> CanvasTransform:
    iw, ih = image_size
    sx = float(draw_w) / max(1, int(iw))
    sy = float(draw_h) / max(1, int(ih))
    return CanvasTransform(x0=float(x0), y0=float(y0), sx=sx, sy=sy)


def apply_global_tweak(
    *,
    rect: Tuple[float, float, float, float],
    layout_tweaks: Dict[str, float],
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> Tuple[float, float, float, float]:
    x, y, w, h = rect
    iw, ih = image_size
    px = iw / 2.0
    py = ih / 2.0

    g_dx = float(layout_tweaks.get("dx", 0.0))
    g_dy = float(layout_tweaks.get("dy", 0.0))
    g_sx = float(layout_tweaks.get("sx", 1.0))
    g_sy = float(layout_tweaks.get("sy", 1.0))

    x = (x - px) * g_sx + px + g_dx
    y = (y - py) * g_sy + py + g_dy
    return x, y, w * g_sx, h * g_sy


def apply_per_key_tweak(
    *,
    key_id: str,
    rect: Tuple[float, float, float, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    inset_default: float,
) -> Tuple[float, float, float, float, float]:
    x, y, w, h = rect
    kt = per_key_layout_tweaks.get(key_id, {}) or {}

    kdx = float(kt.get("dx", 0.0))
    kdy = float(kt.get("dy", 0.0))
    ksx = float(kt.get("sx", 1.0))
    ksy = float(kt.get("sy", 1.0))
    inset_value = float(kt.get("inset", inset_default))

    cx = x + w / 2.0
    cy = y + h / 2.0
    w2 = w * ksx
    h2 = h * ksy
    x2 = cx - (w2 / 2.0) + kdx
    y2 = cy - (h2 / 2.0) + kdy
    return x2, y2, w2, h2, inset_value


def key_canvas_rect(
    *,
    transform: CanvasTransform,
    key: KeyDef,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> Tuple[float, float, float, float, float]:
    """Return key rectangle in canvas coords (without applying inset).

    Returns (x1,y1,x2,y2,inset_value).
    """

    x, y, w, h = (float(v) for v in key.rect)

    gx, gy, gw, gh = apply_global_tweak(
        rect=(x, y, w, h),
        layout_tweaks=layout_tweaks,
        image_size=image_size,
    )

    inset_default = float(layout_tweaks.get("inset", 0.06))
    xk, yk, wk, hk, inset_value = apply_per_key_tweak(
        key_id=key.key_id,
        rect=(gx, gy, gw, gh),
        per_key_layout_tweaks=per_key_layout_tweaks,
        inset_default=inset_default,
    )

    x1, y1, x2, y2 = transform.to_canvas((xk, yk, wk, hk))
    return x1, y1, x2, y2, inset_value


def inset_bbox(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    inset_value: float,
) -> Tuple[float, float, float, float]:
    """Inset a bbox by either fraction (<=0.5) or pixels (>0.5)."""

    w_px = max(0.0, x2 - x1)
    h_px = max(0.0, y2 - y1)
    min_dim = max(1.0, min(w_px, h_px))

    if inset_value <= 0.5:
        inset = min_dim * max(0.0, float(inset_value))
    else:
        inset = max(0.0, float(inset_value))

    inset = min(inset, (min_dim / 2.0) - 1.0)
    inset = max(0.0, inset)

    return x1 + inset, y1 + inset, x2 - inset, y2 - inset


def key_canvas_bbox_inset(
    *,
    transform: CanvasTransform,
    key: KeyDef,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
    inset_value_cap: Optional[float] = None,
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2, inset_value = key_canvas_rect(
        transform=transform,
        key=key,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        image_size=image_size,
    )

    if inset_value_cap is not None:
        inset_value = min(float(inset_value_cap), float(inset_value))

    return inset_bbox(x1=x1, y1=y1, x2=x2, y2=y2, inset_value=float(inset_value))


def hit_test(
    *,
    transform: CanvasTransform,
    x: int,
    y: int,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    keys: Iterable[KeyDef] = REFERENCE_DEVICE_KEYS,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
    inset_value_cap: Optional[float] = None,
) -> Optional[KeyDef]:
    for key in keys:
        x1, y1, x2, y2 = key_canvas_bbox_inset(
            transform=transform,
            key=key,
            layout_tweaks=layout_tweaks,
            per_key_layout_tweaks=per_key_layout_tweaks,
            image_size=image_size,
            inset_value_cap=inset_value_cap,
        )
        if x1 <= x <= x2 and y1 <= y <= y2:
            return key
    return None
