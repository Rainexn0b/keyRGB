from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)

_TK_WIDGET_ERRORS = (RuntimeError, tk.TclError)
_TK_TARGET_ERRORS = _TK_WIDGET_ERRORS + (AttributeError,)
_TK_GEOMETRY_ERRORS = _TK_WIDGET_ERRORS + (TypeError, ValueError)
_TK_SCROLL_ERRORS = _TK_WIDGET_ERRORS + (AttributeError, TypeError, ValueError)


def _log_boundary_exception(key: str, msg: str, exc: Exception) -> None:
    log_throttled(logger, key, interval_s=60, level=logging.DEBUG, msg=msg, exc=exc)


class ScrollableArea:
    def __init__(self, parent: ttk.Frame, *, bg_color: str, padding: int = 16):
        self._canvas = tk.Canvas(parent, highlightthickness=0, bg=bg_color)
        self._vscroll = ttk.Scrollbar(parent, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vscroll.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._vscroll_visible = True
        self._vscroll.pack(side="right", fill="y")

        self.frame = ttk.Frame(self._canvas, padding=padding)
        self._frame_window_id = self._canvas.create_window((0, 0), window=self.frame, anchor="nw")

        self.frame.bind("<Configure>", self._sync_scrollregion)
        self._canvas.bind("<Configure>", self._sync_content_width)

    @property
    def canvas(self) -> tk.Canvas:
        return self._canvas

    def _sync_scrollregion(self, _event=None) -> None:
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except _TK_WIDGET_ERRORS as exc:
            _log_boundary_exception(
                "settings.scrollable_area.sync_scrollregion",
                "Failed to sync settings scrollregion",
                exc,
            )
        self._update_scrollbar_visibility()

    def _sync_content_width(self, event) -> None:
        try:
            self._canvas.itemconfigure(self._frame_window_id, width=event.width)
        except (_TK_WIDGET_ERRORS + (AttributeError,)) as exc:
            _log_boundary_exception(
                "settings.scrollable_area.sync_content_width",
                "Failed to sync settings content width",
                exc,
            )
        self._update_scrollbar_visibility()

    def _content_needs_scroll(self) -> bool:
        try:
            bbox = self._canvas.bbox("all")
            if not bbox:
                return False
            content_h = bbox[3] - bbox[1]
            canvas_h = self._canvas.winfo_height()
            return content_h > max(1, canvas_h)
        except _TK_GEOMETRY_ERRORS as exc:
            _log_boundary_exception(
                "settings.scrollable_area.content_needs_scroll",
                "Failed to inspect settings scrollable area geometry",
                exc,
            )
            return False

    def _update_scrollbar_visibility(self) -> None:
        needs_scroll = self._content_needs_scroll()

        if needs_scroll and not self._vscroll_visible:
            try:
                self._vscroll.pack(side="right", fill="y")
            except _TK_WIDGET_ERRORS as exc:
                _log_boundary_exception(
                    "settings.scrollable_area.show_scrollbar",
                    "Failed to show settings scrollbar",
                    exc,
                )
                return
            self._vscroll_visible = True
        elif (not needs_scroll) and self._vscroll_visible:
            try:
                self._vscroll.pack_forget()
            except _TK_WIDGET_ERRORS as exc:
                _log_boundary_exception(
                    "settings.scrollable_area.hide_scrollbar",
                    "Failed to hide settings scrollbar",
                    exc,
                )
                return
            self._vscroll_visible = False

    @staticmethod
    def _is_descendant(widget: tk.Misc, ancestor: tk.Misc) -> bool:
        cur = widget
        while cur is not None:
            if cur == ancestor:
                return True
            try:
                cur = cur.master  # type: ignore[assignment]
            except _TK_TARGET_ERRORS:
                break
        return False

    @staticmethod
    def _mousewheel_units(event) -> int | None:
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        if not hasattr(event, "delta") or not event.delta:
            return None
        try:
            return int(-1 * (event.delta / 120))
        except (TypeError, ValueError):
            return None

    def bind_mousewheel(self, root: tk.Tk, *, priority_scroll_widget: tk.Misc | None = None) -> None:
        def _on_mousewheel(event) -> str | None:
            x_root = getattr(event, "x_root", None)
            y_root = getattr(event, "y_root", None)
            if x_root is None or y_root is None:
                return None

            try:
                target = root.winfo_containing(x_root, y_root)
            except _TK_WIDGET_ERRORS as exc:
                _log_boundary_exception(
                    "settings.scrollable_area.lookup_target",
                    "Failed to resolve settings mousewheel target",
                    exc,
                )
                return None

            if target is None:
                return None

            try:
                if target.winfo_toplevel() != root:
                    return None
            except _TK_TARGET_ERRORS as exc:
                _log_boundary_exception(
                    "settings.scrollable_area.target_toplevel",
                    "Failed to resolve settings mousewheel toplevel",
                    exc,
                )
                return None

            units = self._mousewheel_units(event)
            if not units:
                return None

            if priority_scroll_widget is not None and self._is_descendant(target, priority_scroll_widget):
                try:
                    priority_scroll_widget.yview_scroll(units, "units")  # type: ignore[attr-defined]
                except _TK_SCROLL_ERRORS as exc:
                    _log_boundary_exception(
                        "settings.scrollable_area.priority_scroll",
                        "Failed to route settings mousewheel to priority widget",
                        exc,
                    )
                    return None
                return "break"

            if self._content_needs_scroll():
                try:
                    self._canvas.yview_scroll(units, "units")
                except _TK_SCROLL_ERRORS as exc:
                    _log_boundary_exception(
                        "settings.scrollable_area.canvas_scroll",
                        "Failed to scroll settings canvas from mousewheel event",
                        exc,
                    )
                    return None
                return "break"

            return None

        root.bind_all("<MouseWheel>", _on_mousewheel)
        root.bind_all("<Button-4>", _on_mousewheel)
        root.bind_all("<Button-5>", _on_mousewheel)

    def finalize_initial_scrollbar_state(self) -> None:
        try:
            bbox = self._canvas.bbox("all")
        except _TK_WIDGET_ERRORS as exc:
            _log_boundary_exception(
                "settings.scrollable_area.initial_bbox",
                "Failed to inspect initial settings scrollable area geometry",
                exc,
            )
            return

        if not bbox:
            return

        try:
            content_h = bbox[3] - bbox[1]
            needs_scroll = content_h > max(1, self._canvas.winfo_height())
        except _TK_GEOMETRY_ERRORS as exc:
            _log_boundary_exception(
                "settings.scrollable_area.initial_needs_scroll",
                "Failed to compute initial settings scrollbar visibility",
                exc,
            )
            return

        if not needs_scroll and self._vscroll_visible:
            try:
                self._vscroll.pack_forget()
            except _TK_WIDGET_ERRORS as exc:
                _log_boundary_exception(
                    "settings.scrollable_area.initial_hide_scrollbar",
                    "Failed to hide initial settings scrollbar",
                    exc,
                )
                return
            self._vscroll_visible = False
