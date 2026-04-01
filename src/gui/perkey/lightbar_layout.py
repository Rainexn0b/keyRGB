from __future__ import annotations

from typing import Any

from src.core.resources.defaults import get_default_lightbar_overlay


def normalize_lightbar_overlay(raw: dict[str, Any] | None) -> dict[str, bool | float]:
    defaults = get_default_lightbar_overlay()
    payload = dict(defaults)
    source = raw if isinstance(raw, dict) else {}
    payload["visible"] = bool(source.get("visible", defaults["visible"]))
    payload["length"] = max(0.20, min(1.0, float(source.get("length", defaults["length"]))))
    payload["thickness"] = max(0.04, min(0.40, float(source.get("thickness", defaults["thickness"]))))
    payload["dx"] = max(-0.50, min(0.50, float(source.get("dx", defaults["dx"]))))
    payload["dy"] = max(-0.50, min(0.50, float(source.get("dy", defaults["dy"]))))
    payload["inset"] = max(0.0, min(0.25, float(source.get("inset", defaults["inset"]))))
    return payload


def lightbar_rect_for_size(
    *,
    width: float,
    height: float,
    overlay: dict[str, Any] | None,
) -> tuple[float, float, float, float] | None:
    payload = normalize_lightbar_overlay(overlay)
    if not bool(payload["visible"]):
        return None

    width = max(1.0, float(width))
    height = max(1.0, float(height))

    margin_x = max(8.0, width * 0.02)
    margin_y = max(10.0, height * 0.03)
    inset_px = float(payload["inset"]) * width
    usable_width = max(24.0, width - (2.0 * margin_x) - (2.0 * inset_px))
    bar_width = max(width * 0.08, usable_width * float(payload["length"]))
    bar_height = max(height * 0.012, height * 0.18 * float(payload["thickness"]))

    center_x = (width / 2.0) + (float(payload["dx"]) * (width * 0.35))
    bottom_y = height - margin_y - inset_px + (float(payload["dy"]) * (height * 0.20))

    x1 = max(margin_x, center_x - (bar_width / 2.0))
    x2 = min(width - margin_x, center_x + (bar_width / 2.0))
    y2 = min(height - margin_y, bottom_y)
    y1 = max(margin_y, y2 - bar_height)
    return (x1, y1, x2, y2)


__all__ = ["lightbar_rect_for_size", "normalize_lightbar_overlay"]