from __future__ import annotations

from dataclasses import dataclass

from src.core.resources.layout import BASE_IMAGE_SIZE


@dataclass
class _OverlayDragContext:
    kid: str
    mode: str
    edges: str
    x: float
    y: float
    dx: float
    dy: float
    sx: float
    sy: float
    gx: float
    gy: float
    gw: float
    gh: float
    l0: float
    r0: float
    t0: float
    b0: float


class OverlayDragController:
    """Stateful overlay drag/resize controller for the per-key canvas."""

    def __init__(self, canvas):
        self._canvas = canvas
        self._ctx: _OverlayDragContext | None = None

    def on_press(self, event) -> None:
        c = self._canvas
        e = c.editor

        if e.overlay_scope.get() != "key":
            self._ctx = None
            return
        if not e.selected_key_id or c._deck_drawn_bbox is None:
            self._ctx = None
            return

        cx = float(event.x)
        cy = float(event.y)

        edges = c._resize_edges_for_point(e.selected_key_id, cx, cy)
        if edges:
            if not c._point_near_key_bbox(e.selected_key_id, cx, cy, pad=6.0):
                self._ctx = None
                return
        else:
            kid = c._hit_test_key_id(cx, cy)
            if kid != e.selected_key_id:
                self._ctx = None
                return

        kt = e.per_key_layout_tweaks.get(e.selected_key_id, {})

        mode = "resize" if edges else "move"

        base_rect = c._key_rect_base_after_global(e.selected_key_id)
        if base_rect is None:
            self._ctx = None
            return
        gx, gy, gw, gh = base_rect

        x2, y2, w2, h2, _inset = c._apply_per_key_tweak(e.selected_key_id, gx, gy, gw, gh)
        l0, r0 = x2, x2 + w2
        t0, b0 = y2, y2 + h2

        self._ctx = _OverlayDragContext(
            kid=e.selected_key_id,
            mode=mode,
            edges=edges,
            x=cx,
            y=cy,
            dx=float(kt.get("dx", 0.0)),
            dy=float(kt.get("dy", 0.0)),
            sx=float(kt.get("sx", 1.0)),
            sy=float(kt.get("sy", 1.0)),
            gx=float(gx),
            gy=float(gy),
            gw=float(gw),
            gh=float(gh),
            l0=float(l0),
            r0=float(r0),
            t0=float(t0),
            b0=float(b0),
        )

    def on_drag(self, event) -> None:
        c = self._canvas
        e = c.editor

        if self._ctx is None or c._deck_drawn_bbox is None:
            return

        kid = self._ctx.kid
        if not kid:
            return

        x0, y0, dw, dh = c._deck_drawn_bbox
        iw, ih = BASE_IMAGE_SIZE
        csx = dw / max(1, iw)
        csy = dh / max(1, ih)
        if csx <= 0 or csy <= 0:
            return

        dx_canvas = float(event.x) - float(self._ctx.x)
        dy_canvas = float(event.y) - float(self._ctx.y)

        dx_base = dx_canvas / csx
        dy_base = dy_canvas / csy

        kt = dict(e.per_key_layout_tweaks.get(kid, {}))
        g_inset = float(e.layout_tweaks.get("inset", 0.06))
        kt.setdefault("inset", float(kt.get("inset", g_inset)))

        if self._ctx.mode == "resize" and self._ctx.edges:
            gx = float(self._ctx.gx)
            gy = float(self._ctx.gy)
            gw = max(1e-6, float(self._ctx.gw))
            gh = max(1e-6, float(self._ctx.gh))

            l0 = float(self._ctx.l0)
            r0 = float(self._ctx.r0)
            t0 = float(self._ctx.t0)
            b0 = float(self._ctx.b0)

            new_l, new_r = l0, r0
            new_t, new_b = t0, b0
            edges = self._ctx.edges
            if "l" in edges:
                new_l = l0 + dx_base
            if "r" in edges:
                new_r = r0 + dx_base
            if "t" in edges:
                new_t = t0 + dy_base
            if "b" in edges:
                new_b = b0 + dy_base

            min_w2 = max(6.0, gw * 0.25)
            min_h2 = max(6.0, gh * 0.25)

            w2 = max(min_w2, new_r - new_l)
            h2 = max(min_h2, new_b - new_t)

            cx_new = new_l + (w2 / 2.0)
            cy_new = new_t + (h2 / 2.0)
            cx_base = gx + (gw / 2.0)
            cy_base = gy + (gh / 2.0)

            new_sx = max(0.3, min(4.0, w2 / gw))
            new_sy = max(0.3, min(4.0, h2 / gh))
            new_dx = cx_new - cx_base
            new_dy = cy_new - cy_base

            kt["sx"] = new_sx
            kt["sy"] = new_sy
            kt["dx"] = new_dx
            kt["dy"] = new_dy

        else:
            kt["dx"] = float(self._ctx.dx) + dx_base
            kt["dy"] = float(self._ctx.dy) + dy_base

        e.per_key_layout_tweaks[kid] = kt
        e.sync_overlay_vars()
        c.redraw()

    def on_release(self, _event) -> None:
        self._ctx = None
