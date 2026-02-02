"""Tray UI refresh helpers."""

from __future__ import annotations

import time
from typing import Any

from ..integrations import runtime
from ..protocols import ensure_tray_icon_state
from . import icon as icon_mod
from . import menu as menu_mod


def _clamp_u8(v: float) -> int:
    return int(max(0, min(255, round(v))))


def _scale_rgb(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    f = float(max(0.0, min(1.0, factor)))
    r, g, b = color
    return (_clamp_u8(r * f), _clamp_u8(g * f), _clamp_u8(b * f))


def _render_visual(visual: icon_mod.IconVisual):
    if visual.mode == "rainbow":
        return icon_mod.create_icon_rainbow(scale=visual.scale, phase=visual.phase)
    if visual.mode == "mosaic":
        return icon_mod.create_icon_mosaic(
            colors_flat=tuple(visual.colors_flat or ()),
            rows=int(visual.rows or 0),
            cols=int(visual.cols or 0),
            scale=visual.scale,
        )
    return icon_mod.create_icon(visual.color or (255, 0, 128))


def _scaled_visual(visual: icon_mod.IconVisual, factor: float) -> icon_mod.IconVisual:
    if visual.mode == "rainbow":
        return icon_mod.IconVisual(mode="rainbow", scale=visual.scale * factor, phase=visual.phase)
    if visual.mode == "mosaic":
        return icon_mod.IconVisual(
            mode="mosaic",
            scale=visual.scale * factor,
            colors_flat=visual.colors_flat,
            rows=visual.rows,
            cols=visual.cols,
        )
    return icon_mod.IconVisual(mode="solid", color=_scale_rgb(visual.color or (0, 0, 0), factor))


def _fade_factor(t: float, *, floor: float = 0.15) -> float:
    """t in [0,1] -> 1..floor..1 (simple triangle)."""
    tt = float(max(0.0, min(1.0, t)))
    if tt <= 0.5:
        a = 1.0 - (tt / 0.5)
    else:
        a = (tt - 0.5) / 0.5
    return float(floor + (1.0 - floor) * a)


def update_icon(tray: Any, *, animate: bool = True) -> None:
    """Update the tray icon image based on current config state."""

    if getattr(tray, "icon", None):
        st = ensure_tray_icon_state(tray)
        now = time.time()
        target = icon_mod.icon_visual(config=tray.config, is_off=tray.is_off, now=now)

        last = st.visual

        # Fast path: no previous state, or animation disabled.
        if not animate or last is None or last == target:
            tray.icon.icon = _render_visual(target)
            st.visual = target
            return

        # Avoid overlapping animations (can happen when multiple pollers/menu actions
        # trigger close together). In that case, just snap to the latest target.
        if st.animating:
            tray.icon.icon = _render_visual(target)
            st.visual = target
            return
        st.animating = True

        try:
            frames = 8
            dt = 0.03

            for i in range(frames):
                t = float(i + 1) / float(frames)
                f = _fade_factor(t)
                # First half fades the previous visual down, second half fades the
                # new visual up.
                if t <= 0.5:
                    frame = _scaled_visual(last, f)
                else:
                    frame = _scaled_visual(target, f)
                tray.icon.icon = _render_visual(frame)
                time.sleep(dt)

            tray.icon.icon = _render_visual(target)
            st.visual = target
        finally:
            st.animating = False


def update_menu(tray: Any) -> None:
    """Rebuild the tray menu from current config/backend state."""

    if getattr(tray, "icon", None):
        tray.config.reload()
        pystray, item = runtime.get_pystray()
        tray.icon.menu = menu_mod.build_menu(tray, pystray=pystray, item=item)


def refresh_ui(tray: Any) -> None:
    """Refresh both icon and menu."""

    update_icon(tray)
    update_menu(tray)
