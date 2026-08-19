from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, SupportsFloat, cast

from keyrgb.core.utils.logging_utils import log_throttled

if TYPE_CHECKING:  # pragma: no cover - typing-only base
    _CanvasBase = tk.Canvas
else:
    _CanvasBase = object

logger = logging.getLogger(__name__)

_CANVAS_MOTION_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, tk.TclError)
_CANVAS_CURSOR_ERRORS = (AttributeError, RuntimeError, tk.TclError)
_CANVAS_CLICK_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, tk.TclError)


class _TkVarProtocol(Protocol):
    def get(self) -> object: ...


class _CanvasEventEditorProtocol(Protocol):
    # Read-only so a concrete StringVar (or any .get() holder) is accepted.
    @property
    def overlay_scope(self) -> _TkVarProtocol: ...

    def on_slot_clicked(self, slot_id: str) -> None: ...


class _SelectedOverlayIdentityGetter(Protocol):
    def _selected_overlay_identity(self) -> object: ...


class _SelectedSlotIdHolder(Protocol):
    selected_slot_id: object | None


class _SelectedKeyIdHolder(Protocol):
    selected_key_id: object | None


class _SlotIdForKeyIdLookup(Protocol):
    def _slot_id_for_key_id(self, key_id: str) -> object: ...


class _HitTestSlotIdSurface(Protocol):
    def _hit_test_slot_id(self, x: float, y: float) -> str | None: ...


class _CursorForEdges(Protocol):
    def __call__(self, edges: str) -> str: ...


class _PointInKeyBbox(Protocol):
    def __call__(self, identity: str, cx: float, cy: float) -> bool: ...


class _ResizeEdgesForPoint(Protocol):
    def __call__(self, identity: str, cx: float, cy: float) -> str: ...


class _CanvasPointEvent(Protocol):
    # Read-only properties so tkinter Event (x: int / y: int) satisfies this
    # protocol: mutable attribute members would be invariant and reject int
    # against SupportsFloat.
    @property
    def x(self) -> SupportsFloat: ...

    @property
    def y(self) -> SupportsFloat: ...


def _selected_overlay_identity_or_none(editor: object) -> str | None:
    try:
        identity_getter = cast(_SelectedOverlayIdentityGetter, editor)._selected_overlay_identity
    except AttributeError:
        return None
    if not callable(identity_getter):
        return None
    selected_identity = identity_getter()
    if not selected_identity:
        return None
    return str(selected_identity)


def _selected_slot_id_or_none(editor: object) -> str | None:
    try:
        selected_slot_id = cast(_SelectedSlotIdHolder, editor).selected_slot_id
    except AttributeError:
        return None
    if not selected_slot_id:
        return None
    return str(selected_slot_id)


def _selected_key_id_or_none(editor: object) -> str | None:
    try:
        selected_key_id = cast(_SelectedKeyIdHolder, editor).selected_key_id
    except AttributeError:
        return None
    if not selected_key_id:
        return None
    return str(selected_key_id)


def _slot_id_for_key_id_or_none(editor: object, key_id: str) -> str | None:
    try:
        slot_lookup = cast(_SlotIdForKeyIdLookup, editor)._slot_id_for_key_id
    except AttributeError:
        return None
    if not callable(slot_lookup):
        return None
    resolved_slot_id = slot_lookup(key_id)
    if not resolved_slot_id:
        return None
    return str(resolved_slot_id)


def _hit_test_slot_id_or_none(canvas: object, *, x: float, y: float) -> str | None:
    try:
        hit_test = cast(_HitTestSlotIdSurface, canvas)._hit_test_slot_id
    except AttributeError:
        return None
    if not callable(hit_test):
        return None
    return hit_test(x, y)


class _KeyboardCanvasEventMixin(_CanvasBase):
    # Attributes/methods provided by KeyboardCanvas (the concrete subclass).
    # tk.Canvas members (after, configure, find_withtag, gettags, ...) come
    # from the check-time-only _CanvasBase so they carry the real tkinter
    # stub signatures instead of shadow protocols.
    editor: _CanvasEventEditorProtocol
    _resize_job: str | None
    _cursor_for_edges: _CursorForEdges
    _point_in_key_bbox: _PointInKeyBbox
    redraw: Callable[[], None]
    _resize_edges_for_point: _ResizeEdgesForPoint

    def _selected_slot_identity(self) -> str | None:
        selected_identity = _selected_overlay_identity_or_none(self.editor)
        if selected_identity is not None:
            return selected_identity

        selected_slot_id = _selected_slot_id_or_none(self.editor)
        if selected_slot_id is not None:
            return selected_slot_id

        selected_key_id = _selected_key_id_or_none(self.editor)
        if selected_key_id is None:
            return None

        resolved_slot_id = _slot_id_for_key_id_or_none(self.editor, selected_key_id)
        if resolved_slot_id is not None:
            return resolved_slot_id
        return str(selected_key_id)

    def _on_resize(self, _event: object) -> None:
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

    def _on_motion(self, event: _CanvasPointEvent) -> None:
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
        except _CANVAS_MOTION_ERRORS as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_motion",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error in perkey hover handling",
                exc=exc,
            )

    def _on_leave(self, _event: object) -> None:
        try:
            self.configure(cursor="")
        except _CANVAS_CURSOR_ERRORS as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_leave",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error resetting cursor",
                exc=exc,
            )

    def _on_click(self, event: _CanvasPointEvent) -> None:
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
                        slot_id = _slot_id_for_key_id_or_none(self.editor, key_id)
                        self.editor.on_slot_clicked(str(slot_id or key_id))
                        return
        except _CANVAS_CLICK_ERRORS as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_click",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error handling click",
                exc=exc,
            )

        slot_id = _hit_test_slot_id_or_none(self, x=float(event.x), y=float(event.y))
        if slot_id is not None:
            self.editor.on_slot_clicked(slot_id)


# These imports are only for type checkers.
# They keep the mixin self-contained without causing runtime import cycles.
if False:  # pragma: no cover
    from ..canvas import KeyboardCanvas  # noqa: F401
