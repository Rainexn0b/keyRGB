from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable

from src.gui.theme import detect_system_prefers_dark


class UpwardListboxDropdown:
    def __init__(
        self,
        root: tk.Misc,
        anchor: tk.Widget,
        values_provider: Callable[[], Iterable[str]],
        get_current_value: Callable[[], str],
        set_value: Callable[[str], None],
        bg: str,
        fg: str,
    ) -> None:
        self._root = root
        self._anchor = anchor
        self._values_provider = values_provider
        self._get_current_value = get_current_value
        self._set_value = set_value
        self._bg = bg
        self._fg = fg
        self._win: tk.Toplevel | None = None

    def is_open(self) -> bool:
        return self._win is not None

    def close(self, _e=None) -> None:
        win = self._win
        if win is None:
            return
        # Mark closed early to avoid re-entrancy issues (e.g. multiple FocusOut / clicks).
        self._win = None
        try:
            win.grab_release()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass

    def open(self, _e=None) -> str:
        if self._win is not None:
            self.close()
            return "break"

        values = list(self._values_provider())
        if not values:
            return "break"

        popup = tk.Toplevel(self._root)
        popup.withdraw()
        popup.transient(self._root)
        popup.overrideredirect(True)

        # Hint to the WM that this is a combo/dropdown (helps with z-order/focus on Linux).
        try:
            popup.attributes("-type", "combo")
        except Exception:
            pass

        try:
            popup.configure(bg=self._bg)
        except Exception:
            pass

        # Selection color for hover feedback
        prefers_dark = detect_system_prefers_dark()
        sel_bg = "#4a4a4a" if prefers_dark is not False else "#3399ff"
        sel_fg = "#ffffff"

        lb = tk.Listbox(
            popup,
            exportselection=False,
            activestyle="none",
            height=min(len(values), 10),
            bg=self._bg,
            fg=self._fg,
            selectbackground=sel_bg,
            selectforeground=sel_fg,
            highlightthickness=1,
            relief="solid",
            borderwidth=1,
        )
        lb.pack(fill="both", expand=True)

        for v in values:
            lb.insert("end", v)

        current = (self._get_current_value() or "").strip()
        if current in values:
            idx = values.index(current)
            try:
                lb.selection_set(idx)
                lb.activate(idx)
                lb.see(idx)
            except Exception:
                pass

        def _commit(_event=None) -> None:
            try:
                sel = lb.curselection()
                if not sel:
                    self.close()
                    return
                chosen = str(lb.get(sel[0]))
            except Exception:
                self.close()
                return
            self._set_value(chosen)
            self.close()

        def _on_motion(event) -> None:
            try:
                index = lb.nearest(event.y)
                if index >= 0:
                    lb.selection_clear(0, "end")
                    lb.selection_set(index)
                    lb.activate(index)
            except Exception:
                pass

        lb.bind("<Motion>", _on_motion)
        lb.bind("<ButtonRelease-1>", _commit)
        lb.bind("<Return>", _commit)
        lb.bind("<Escape>", self.close)
        lb.bind("<FocusOut>", lambda e: self.close())

        popup.update_idletasks()

        x = self._anchor.winfo_rootx()
        y = self._anchor.winfo_rooty()
        w = self._anchor.winfo_width()
        h = popup.winfo_reqheight()

        y_above = y - h
        if y_above < 0:
            y_above = y + self._anchor.winfo_height()

        popup.geometry(f"{max(60, w)}x{h}+{x}+{y_above}")
        popup.deiconify()
        popup.lift()

        try:
            popup.grab_set()
        except Exception:
            pass

        try:
            popup.focus_force()
        except Exception:
            pass
        lb.focus_set()

        def _check_click_outside(event) -> None:
            try:
                if event.widget == lb:
                    return
                self.close()
            except Exception:
                self.close()

        popup.bind("<Button-1>", _check_click_outside)

        # If the app is closing while the popup is open, ensure we release the grab cleanly.
        try:
            self._root.bind("<Destroy>", self.close, add=True)
        except Exception:
            pass

        self._win = popup
        return "break"
