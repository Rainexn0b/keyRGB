"""Tray UI refresh helpers."""

from __future__ import annotations

import time
from typing import Protocol, cast

from ..integrations import runtime
from ..protocols import ensure_tray_icon_state
from . import icon as icon_mod
from . import menu as menu_mod, menu_sections


class _ReloadableConfigProtocol(icon_mod.TrayIconConfig, Protocol):
    def reload(self) -> None: ...


class _IconRefreshTrayProtocol(Protocol):
    config: icon_mod.TrayIconConfig
    is_off: bool


class _MenuRefreshTrayProtocol(Protocol):
    config: _ReloadableConfigProtocol


class _TrayIconImageSurfaceProtocol(Protocol):
    icon: object


class _TrayIconMenuSurfaceProtocol(Protocol):
    menu: object


class _MenuFactoryProtocol(Protocol):
    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _MenuItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


def _icon_refresh_tray(tray: object) -> _IconRefreshTrayProtocol:
    return cast(_IconRefreshTrayProtocol, tray)


def _menu_refresh_tray(tray: object) -> _MenuRefreshTrayProtocol:
    return cast(_MenuRefreshTrayProtocol, tray)


def _icon_surface(icon: object | None) -> _TrayIconImageSurfaceProtocol | None:
    if not icon:
        return None
    return cast(_TrayIconImageSurfaceProtocol, icon)


def _menu_surface(icon: object | None) -> _TrayIconMenuSurfaceProtocol | None:
    if not icon:
        return None
    return cast(_TrayIconMenuSurfaceProtocol, icon)


def _menu_runtime() -> tuple[menu_sections._PystrayProtocol, menu_sections._ItemFactoryProtocol]:
    pystray, item = runtime.get_pystray()
    return cast(menu_sections._PystrayProtocol, pystray), cast(menu_sections._ItemFactoryProtocol, item)


def _clamp_u8(v: float) -> int:
    return int(max(0, min(255, round(v))))


def _scale_rgb(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    f = float(max(0.0, min(1.0, factor)))
    r, g, b = color
    return (_clamp_u8(r * f), _clamp_u8(g * f), _clamp_u8(b * f))


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


def update_icon(tray: object, *, animate: bool = True) -> None:
    """Update the tray icon image based on current config state."""

    tray_icon = _icon_surface(getattr(tray, "icon", None))
    if tray_icon is None:
        return

    typed_tray = _icon_refresh_tray(tray)
    st = ensure_tray_icon_state(tray)
    now = time.time()
    target = icon_mod.icon_visual(
        config=typed_tray.config,
        is_off=typed_tray.is_off,
        now=now,
        backend=getattr(tray, "backend", None),
    )

    last = st.visual

    # Fast path: no previous state, or animation disabled.
    if not animate or last is None or last == target:
        tray_icon.icon = icon_mod.render_icon_visual(target)
        st.visual = target
        return

    # Avoid overlapping animations (can happen when multiple pollers/menu actions
    # trigger close together). In that case, just snap to the latest target.
    if st.animating:
        tray_icon.icon = icon_mod.render_icon_visual(target)
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
            tray_icon.icon = icon_mod.render_icon_visual(frame)
            time.sleep(dt)

        tray_icon.icon = icon_mod.render_icon_visual(target)
        st.visual = target
    finally:
        st.animating = False


def update_menu(tray: object) -> None:
    """Rebuild the tray menu from current config/backend state."""

    tray_icon = _menu_surface(getattr(tray, "icon", None))
    if tray_icon is None:
        return

    typed_tray = _menu_refresh_tray(tray)
    typed_tray.config.reload()
    pystray, item = _menu_runtime()
    tray_icon.menu = menu_mod.build_menu(tray, pystray=pystray, item=item)


def refresh_ui(tray: object) -> None:
    """Refresh both icon and menu."""

    update_icon(tray)
    update_menu(tray)
