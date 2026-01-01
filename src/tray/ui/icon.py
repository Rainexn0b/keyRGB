from __future__ import annotations

import colorsys
import time
from typing import Any, Mapping

from PIL import Image, ImageDraw


def create_icon(color: tuple[int, int, int]) -> Image.Image:
    """Create tray icon image."""

    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle((8, 20, 56, 44), outline=(*color, 255), width=2)
    for row in range(2):
        for col in range(6):
            x = 12 + col * 7
            y = 24 + row * 8
            draw.rectangle(
                (x, y, x + 5, y + 5),
                fill=(*color, 255),
                outline=(*color, 255),
                width=1,
            )

    return img


def representative_color(
    *,
    config: Any,
    is_off: bool,
    now: float | None = None,
) -> tuple[int, int, int]:
    """Pick an RGB color representative of the currently applied state."""

    if now is None:
        now = time.time()

    # Off state
    if is_off or getattr(config, "brightness", 0) == 0:
        return (64, 64, 64)

    effect = str(getattr(config, "effect", "none") or "none")
    brightness = int(getattr(config, "brightness", 25) or 25)

    # Per-key: average of configured colors
    if effect == "perkey":
        try:
            values = list(getattr(config, "per_key_colors", {}).values())
        except Exception:
            values = []

        if values:
            r = int(round(sum(c[0] for c in values) / len(values)))
            g = int(round(sum(c[1] for c in values) / len(values)))
            b = int(round(sum(c[2] for c in values) / len(values)))
            base = (r, g, b)
        else:
            base = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))

    # Multi-color effects: cycle a hue so the icon changes.
    elif effect in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}:
        speed = int(getattr(config, "speed", 5) or 5)
        rate = 0.05 + 0.10 * (max(0, min(10, speed)) / 10.0)
        hue = (now * rate) % 1.0
        rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        base = (int(rr * 255), int(gg * 255), int(bb * 255))

    else:
        base = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))

    # Scale by brightness (0..50). Keep a minimum so the icon stays visible.
    scale = max(0.25, min(1.0, brightness / 50.0))
    return (
        int(max(0, min(255, base[0] * scale))),
        int(max(0, min(255, base[1] * scale))),
        int(max(0, min(255, base[2] * scale))),
    )
