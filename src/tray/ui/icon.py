from __future__ import annotations

import colorsys
import math
import time
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from src.gui.theme.detect import detect_system_prefers_dark
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid


_ICON_SIZE = (64, 64)
_ICON_INNER_SIZE = (56, 56)


def _candidate_tray_logo_paths() -> list[Path]:
    paths: list[Path] = []

    # Repo checkout (and editable installs) typically keep assets/ alongside src/.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "logo-tray.png"
        if cand not in paths:
            paths.append(cand)

    # Working-directory fallback (useful for some launchers/tests).
    try:
        paths.append(Path.cwd() / "assets" / "logo-tray.png")
    except Exception:
        pass

    # Support common system install locations so packaged builds (Flatpak/RPM/AppImage)
    # can still find the asset when it's installed to a system directory.
    for sys_cand in (
        Path("/usr/share/keyrgb/assets/logo-tray.png"),
        Path("/usr/lib/keyrgb/assets/logo-tray.png"),
        Path("/usr/local/share/keyrgb/assets/logo-tray.png"),
        Path("/usr/local/lib/keyrgb/assets/logo-tray.png"),
    ):
        if sys_cand not in paths:
            paths.append(sys_cand)

    return paths


@lru_cache(maxsize=1)
def _load_tray_logo_alpha_64() -> Image.Image | None:
    for p in _candidate_tray_logo_paths():
        try:
            if not p.is_file():
                continue
        except Exception:
            continue

        try:
            img = Image.open(p).convert("RGBA")
            resampling = getattr(getattr(Image, "Resampling", None), "LANCZOS", getattr(Image, "LANCZOS", 1))

            # Keep a small transparent margin so the icon doesn't look like a
            # solid square in the tray (resizing a high-res asset directly to
            # 64×64 tends to eliminate edge transparency).
            inner = img.resize(_ICON_INNER_SIZE, resampling)  # type: ignore[arg-type]
            out = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
            ox = (_ICON_SIZE[0] - _ICON_INNER_SIZE[0]) // 2
            oy = (_ICON_SIZE[1] - _ICON_INNER_SIZE[1]) // 2
            out.alpha_composite(inner, dest=(ox, oy))

            # Return only the alpha channel; we colorize at render time so we can
            # invert the outline color in light mode.
            return out.getchannel("A")
        except Exception:
            continue
    return None


def _outline_color_for_theme() -> tuple[int, int, int]:
    # Default stays as a light outline (optimized for dark trays), matching the
    # historical default of dark mode when detection is unknown.
    base = (235, 235, 235)
    try:
        prefers_dark = detect_system_prefers_dark()
    except Exception:
        prefers_dark = None

    # If the system prefers light, invert to a dark outline so it's visible.
    if prefers_dark is False:
        return (255 - base[0], 255 - base[1], 255 - base[2])
    return base


@lru_cache(maxsize=4)
def _tray_logo_outline(outline_color: tuple[int, int, int]) -> Image.Image | None:
    alpha64 = _load_tray_logo_alpha_64()
    if alpha64 is None:
        return None
    outline = Image.new("RGBA", _ICON_SIZE, color=(*outline_color, 0))
    outline.putalpha(alpha64)
    return outline


@lru_cache(maxsize=1)
def _tray_logo_masks() -> tuple[Image.Image, Image.Image] | None:
    """Return (silhouette_mask, cutout_mask) for the tray logo.

    - silhouette_mask keeps the full outer logo silhouette (including internal holes)
      so we can preserve non-square transparency when needed.
    - cutout_mask isolates internal transparent regions (the "K" cutout), so we can
      place dynamic color only behind the cutout and avoid color bleeding at the
      outer edges of the logo.
    """

    alpha = _load_tray_logo_alpha_64()
    if alpha is None:
        return None

    w, h = alpha.size
    a = list(alpha.getdata())

    def idx(x: int, y: int) -> int:
        return y * w + x

    transparent = [v == 0 for v in a]
    external = [False] * (w * h)
    q: deque[tuple[int, int]] = deque()

    # Seed border pixels.
    for x in range(w):
        for y in (0, h - 1):
            i = idx(x, y)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            i = idx(x, y)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((x, y))

    # Flood-fill external transparency.
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            i = idx(nx, ny)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((nx, ny))

    # Silhouette = everything that's *not* external background.
    silhouette_data = [0 if external[i] else 255 for i in range(w * h)]
    silhouette = Image.new("L", (w, h), color=0)
    silhouette.putdata(silhouette_data)

    # Cutout = internal transparent pixels (transparent but not external background).
    cutout_data = [255 if (transparent[i] and not external[i]) else 0 for i in range(w * h)]
    cutout = Image.new("L", (w, h), color=0)
    cutout.putdata(cutout_data)

    return (silhouette, cutout)


def create_icon(color: tuple[int, int, int]) -> Image.Image:
    """Create tray icon image."""

    logo = _tray_logo_outline(_outline_color_for_theme())
    masks = _tray_logo_masks()
    if logo is not None and masks is not None:
        _silhouette_mask, cutout_mask = masks

        # Only show dynamic color through the internal cutout (the transparent "K").
        # This avoids tinted halos at the outer logo edges caused by anti-aliasing.
        underlay = Image.new("RGBA", _ICON_SIZE, color=(*color, 255))
        underlay.putalpha(cutout_mask)

        out = underlay.copy()
        out.alpha_composite(logo)
        return out

    # Fallback: old placeholder keyboard icon.
    img = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
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

    def _pace_from_speed(speed: int) -> float:
        # Mirror src.core.effects.software.base.pace(engine) mapping.
        s = max(0, min(10, int(speed)))
        t = float(s) / 10.0
        t = t * t
        return float(0.25 + (10.0 - 0.25) * t)

    def _weighted_hsv_mean(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
        # Avoid muddy greys when averaging multi-color maps by averaging hue on the
        # unit circle and weighting by saturation/value.
        total = 0.0
        x = 0.0
        y = 0.0
        s_acc = 0.0
        v_acc = 0.0

        for r, g, b in colors:
            rr = max(0, min(255, int(r))) / 255.0
            gg = max(0, min(255, int(g))) / 255.0
            bb = max(0, min(255, int(b))) / 255.0
            h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
            if v <= 0.0:
                continue
            w = max(1e-6, s * v)
            ang = 2.0 * math.pi * h
            x += math.cos(ang) * w
            y += math.sin(ang) * w
            s_acc += s * w
            v_acc += v * w
            total += w

        if total <= 1e-6 or (x == 0.0 and y == 0.0):
            if not colors:
                return (255, 0, 128)
            r = int(round(sum(c[0] for c in colors) / len(colors)))
            g = int(round(sum(c[1] for c in colors) / len(colors)))
            b = int(round(sum(c[2] for c in colors) / len(colors)))
            return (r, g, b)

        mean_h = (math.atan2(y, x) / (2.0 * math.pi)) % 1.0
        mean_s = max(0.0, min(1.0, s_acc / total))
        mean_v = max(0.0, min(1.0, v_acc / total))
        rr, gg, bb = colorsys.hsv_to_rgb(mean_h, mean_s, mean_v)
        return (int(rr * 255), int(gg * 255), int(bb * 255))

    if now is None:
        now = time.time()

    # Off state
    if is_off or getattr(config, "brightness", 0) == 0:
        return (64, 64, 64)

    effect = str(getattr(config, "effect", "none") or "none")
    brightness = int(getattr(config, "brightness", 25) or 25)

    # Reactive typing effects: the base color can be black while idle (which
    # makes the tray icon disappear in dark mode). Prefer the reactive color
    # when available and fall back to a visible accent color.
    is_reactive = effect.startswith("reactive_")
    # NOTE: For the tray icon we intentionally follow the profile/policy
    # brightness (config.brightness). Reactive pulse intensity is tracked
    # separately via config.reactive_brightness.

    # Per-key: average of configured colors
    if effect == "perkey":
        try:
            brightness = int(getattr(config, "perkey_brightness", brightness) or brightness)
        except Exception:
            pass

        base_color = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))
        try:
            per_key = dict(getattr(config, "per_key_colors", {}) or {})
        except Exception:
            per_key = {}

        # Build the same full grid used by the per-key pipeline, then pick a
        # representative color using a weighted HSV mean (cheap, but avoids grey).
        try:
            full = build_full_color_grid(
                base_color=base_color,
                per_key_colors=per_key,
                num_rows=NUM_ROWS,
                num_cols=NUM_COLS,
            )
            base = _weighted_hsv_mean(list(full.values()))
        except Exception:
            values = list(per_key.values())
            base = _weighted_hsv_mean(values) if values else base_color

    # Multi-color effects: cycle a hue so the icon changes.
    elif effect in {"rainbow_wave", "rainbow_swirl", "spectrum_cycle", "color_cycle"}:
        speed = int(getattr(config, "speed", 5) or 5)
        p = _pace_from_speed(speed)

        if effect == "rainbow_wave":
            hue = (now * (0.165 * p)) % 1.0
            col_den = float(max(1, NUM_COLS - 1))
            row_den = float(max(1, NUM_ROWS - 1))
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            position = (float(c) / col_den) + (0.18 * (float(r) / row_den))
            h = (hue + position) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "rainbow_swirl":
            hue = (now * (0.115 * p)) % 1.0
            cr = (NUM_ROWS - 1) / 2.0
            cc = (NUM_COLS - 1) / 2.0
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            dy = float(r) - cr
            dx = float(c) - cc
            ang = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
            rad = math.hypot(dx, dy)
            max_r = math.hypot(max(cc, NUM_COLS - 1 - cc), max(cr, NUM_ROWS - 1 - cr))
            max_r = max(1e-6, max_r)
            h = (hue + ang + 0.25 * (rad / max_r)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "color_cycle":
            phase = now * (1.8 * p)
            r = (math.sin(phase) + 1.0) / 2.0
            g = (math.sin(phase + (2.0 * math.pi / 3.0)) + 1.0) / 2.0
            b = (math.sin(phase + (4.0 * math.pi / 3.0)) + 1.0) / 2.0
            base = (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

        else:  # spectrum_cycle
            hue = (now * (0.22 * p)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

    elif effect in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}:
        # Hardware and mixed effects: keep a cheap animated approximation.
        speed = int(getattr(config, "speed", 5) or 5)
        p = _pace_from_speed(speed)
        hue = (now * (0.18 * p)) % 1.0
        rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        base = (int(rr * 255), int(gg * 255), int(bb * 255))

    else:
        if is_reactive:
            base = tuple(
                getattr(config, "reactive_color", None)
                or getattr(config, "color", None)
                or (255, 0, 128)
            )
            try:
                if tuple(base) == (0, 0, 0):
                    base = (255, 0, 128)
            except Exception:
                base = (255, 0, 128)
        else:
            base = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))

    # Scale by brightness (0..50), but bias brighter than the keyboard so the
    # tray icon stays readable in dark mode at low keyboard brightness.
    #
    # Ratio: approximately 1:3 (keyboard:icon), clamped to [0.25, 1.0].
    icon_brightness = max(0, min(50, int(round(float(brightness) * 3.0))))
    scale = max(0.25, min(1.0, icon_brightness / 50.0))
    return (
        int(max(0, min(255, base[0] * scale))),
        int(max(0, min(255, base[1] * scale))),
        int(max(0, min(255, base[2] * scale))),
    )
