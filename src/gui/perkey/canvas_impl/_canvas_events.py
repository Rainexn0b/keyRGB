from __future__ import annotations

import logging
import tkinter as tk
from typing import Any

from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)


class _KeyboardCanvasEventMixin:
    # Attributes/methods provided by tk.Canvas and KeyboardCanvas
    editor: Any
    _resize_job: Any
    after: Any
    after_cancel: Any
    configure: Any
    find_withtag: Any
    gettags: Any
    _cursor_for_edges: Any
    _point_in_key_bbox: Any
    redraw: Any
    _resize_edges_for_point: Any

    def _selected_slot_identity(self) -> str | None:
        identity_getter = getattr(self.editor, "_selected_overlay_identity", None)
        selected_identity = identity_getter() if callable(identity_getter) else None
        if selected_identity:
            return str(selected_identity)

        selected_slot_id = getattr(self.editor, "selected_slot_id", None)
        if selected_slot_id:
            return str(selected_slot_id)

        selected_key_id = getattr(self.editor, "selected_key_id", None)
        if not selected_key_id:
            return None

        slot_lookup = getattr(self.editor, "_slot_id_for_key_id", None)
        if callable(slot_lookup):
            resolved_slot_id = slot_lookup(selected_key_id)
            if resolved_slot_id:
                return str(resolved_slot_id)
        return str(selected_key_id)

    def _on_resize(self, _event) -> None:
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError as exc:
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
            selected_slot_id = self._selected_slot_identity()
            if self.editor.overlay_scope.get() != "key" or not selected_slot_id:
                self.configure(cursor="")
                return

            cx = float(event.x)
            cy = float(event.y)
            edges = self._resize_edges_for_point(selected_slot_id, cx, cy)
            if edges:
                self.configure(cursor=self._cursor_for_edges(edges))
                return

            # Inside selected key: show move cursor.
            if self._point_in_key_bbox(selected_slot_id, cx, cy):
                self.configure(cursor="fleur")
            else:
                self.configure(cursor="")
        except Exception as exc:  # @quality-exception exception-transparency: motion handler coordinates Tk geometry calls; must stay non-fatal
            log_throttled(
                logger,
                "perkey.canvas.on_motion",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error in perkey hover handling",
                exc=exc,
            )

    def _on_leave(self, _event) -> None:
        try:
            self.configure(cursor="")
        except Exception as exc:  # @quality-exception exception-transparency: on_leave cursor reset is a Tk widget call; must stay non-fatal
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
                    if t.startswith("pslot_"):
                        self.editor.on_slot_clicked(t.removeprefix("pslot_"))
                        return
                    if t.startswith("pkey_"):
                        key_id = t.removeprefix("pkey_")
                        slot_lookup = getattr(self.editor, "_slot_id_for_key_id", None)
                        slot_id = slot_lookup(key_id) if callable(slot_lookup) else None
                        self.editor.on_slot_clicked(str(slot_id or key_id))
                        return
        except Exception as exc:  # @quality-exception exception-transparency: Tk canvas tag lookup and slot dispatch; must stay non-fatal
            log_throttled(
                logger,
                "perkey.canvas.on_click",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error handling click",
                exc=exc,
            )

        hit_test = getattr(self, "_hit_test_slot_id", None)
        slot_id = hit_test(float(event.x), float(event.y)) if callable(hit_test) else None
        if slot_id is not None:
            self.editor.on_slot_clicked(slot_id)


# These imports are only for type checkers.
# They keep the mixin self-contained without causing runtime import cycles.
if False:  # pragma: no cover
    from ..canvas import KeyboardCanvas  # noqa: F401
