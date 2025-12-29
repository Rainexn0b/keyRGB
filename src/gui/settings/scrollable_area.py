from __future__ import annotations

import tkinter as tk
from tkinter import ttk


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
        except Exception:
            pass
        self._update_scrollbar_visibility()

    def _sync_content_width(self, event) -> None:
        try:
            self._canvas.itemconfigure(self._frame_window_id, width=event.width)
        except Exception:
            pass
        self._update_scrollbar_visibility()

    def _content_needs_scroll(self) -> bool:
        try:
            bbox = self._canvas.bbox("all")
            if not bbox:
                return False
            content_h = bbox[3] - bbox[1]
            canvas_h = self._canvas.winfo_height()
            return content_h > max(1, canvas_h)
        except Exception:
            return False

    def _update_scrollbar_visibility(self) -> None:
        try:
            needs_scroll = self._content_needs_scroll()

            if needs_scroll and not self._vscroll_visible:
                self._vscroll.pack(side="right", fill="y")
                self._vscroll_visible = True
            elif (not needs_scroll) and self._vscroll_visible:
                self._vscroll.pack_forget()
                self._vscroll_visible = False
        except Exception:
            pass

    @staticmethod
    def _is_descendant(widget: tk.Misc, ancestor: tk.Misc) -> bool:
        cur = widget
        while cur is not None:
            if cur == ancestor:
                return True
            try:
                cur = cur.master  # type: ignore[assignment]
            except Exception:
                break
        return False

    def bind_mousewheel(self, root: tk.Tk, *, priority_scroll_widget: tk.Misc | None = None) -> None:
        def _on_mousewheel(event) -> str | None:
            try:
                x_root = getattr(event, "x_root", None)
                y_root = getattr(event, "y_root", None)
                if x_root is None or y_root is None:
                    return None

                target = root.winfo_containing(x_root, y_root)
                if target is None or target.winfo_toplevel() != root:
                    return None

                units: int | None = None
                if getattr(event, "num", None) == 4:
                    units = -1
                elif getattr(event, "num", None) == 5:
                    units = 1
                elif hasattr(event, "delta") and event.delta:
                    units = int(-1 * (event.delta / 120))

                if not units:
                    return None

                if priority_scroll_widget is not None and self._is_descendant(target, priority_scroll_widget):
                    try:
                        priority_scroll_widget.yview_scroll(units, "units")  # type: ignore[attr-defined]
                        return "break"
                    except Exception:
                        return None

                if self._content_needs_scroll():
                    self._canvas.yview_scroll(units, "units")
                    return "break"

                return None
            except Exception:
                return None

        root.bind_all("<MouseWheel>", _on_mousewheel)
        root.bind_all("<Button-4>", _on_mousewheel)
        root.bind_all("<Button-5>", _on_mousewheel)

    def finalize_initial_scrollbar_state(self) -> None:
        try:
            bbox = self._canvas.bbox("all")
            if bbox:
                content_h = bbox[3] - bbox[1]
                needs_scroll = content_h > max(1, self._canvas.winfo_height())
                if not needs_scroll and self._vscroll_visible:
                    self._vscroll.pack_forget()
                    self._vscroll_visible = False
        except Exception:
            pass
