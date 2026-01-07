from __future__ import annotations

import logging

from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)


class _KeyboardCanvasEventMixin:
    def _on_resize(self, _event) -> None:
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception as exc:
                log_throttled(
                    logger,
                    "perkey.canvas.after_cancel",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="after_cancel failed",
                    exc=exc,
                )
        self._resize_job = self.after(40, self._redraw_callback)

    def _redraw_callback(self) -> None:
        self._resize_job = None
        self.redraw()

    def _on_motion(self, event) -> None:
        # Cursor affordances for overlay move/resize.
        try:
            if self.editor.overlay_scope.get() != "key" or not self.editor.selected_key_id:
                self.configure(cursor="")
                return

            cx = float(event.x)
            cy = float(event.y)
            edges = self._resize_edges_for_point(self.editor.selected_key_id, cx, cy)
            if edges:
                self.configure(cursor=self._cursor_for_edges(edges))
                return

            # Inside selected key: show move cursor.
            if self._point_in_key_bbox(self.editor.selected_key_id, cx, cy):
                self.configure(cursor="fleur")
            else:
                self.configure(cursor="")
        except Exception:
            log_throttled(
                logger,
                "perkey.canvas.on_motion",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error in perkey hover handling",
            )

    def _on_leave(self, _event) -> None:
        try:
            self.configure(cursor="")
        except Exception as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_leave",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error resetting cursor",
                exc=exc,
            )

    def _on_click(self, event) -> None:
        try:
            current = self.find_withtag("current")
            if current:
                tags = self.gettags(current[0])
                for t in tags:
                    if t.startswith("pkey_"):
                        self.editor.on_key_clicked(t.removeprefix("pkey_"))
                        return
        except Exception as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_click",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error handling click",
                exc=exc,
            )

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid is not None:
            self.editor.on_key_clicked(kid)


# These imports are only for type checkers.
# They keep the mixin self-contained without causing runtime import cycles.
if False:  # pragma: no cover
    from ..canvas import KeyboardCanvas  # noqa: F401
