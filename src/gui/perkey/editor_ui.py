from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.core.profile import profiles
from src.gui.widgets.color_wheel import ColorWheel

from .canvas import KeyboardCanvas
from .overlay import OverlayControls


class _UpwardListboxDropdown:
    def __init__(
        self,
        root: tk.Misc,
        anchor: tk.Widget,
        values_provider,
        get_current_value,
        set_value,
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
        sel_bg = "#4a4a4a" if self._bg == "#2b2b2b" else "#3399ff"
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


def build_editor_ui(editor) -> None:
    main = ttk.Frame(editor.root, padding=16)
    main.pack(fill="both", expand=True)

    # Status row (full-width) so messages don't get clipped by the right panel.
    status_row = ttk.Frame(main)
    status_row.pack(fill="x", pady=(0, 10))

    editor.status_label = ttk.Label(
        status_row,
        text="Click a key to start",
        font=("Sans", 9),
        anchor="w",
        justify="left",
    )
    editor.status_label.pack(fill="x")

    def _sync_status_wrap(_e=None) -> None:
        try:
            # Wrap to the available width, accounting for padding.
            w = int(status_row.winfo_width())
            editor.status_label.configure(wraplength=max(200, w - 8))
        except Exception:
            return

    # Ensure wrapping stays correct when the window is resized.
    try:
        editor.root.bind("<Configure>", _sync_status_wrap, add=True)
    except Exception:
        pass
    editor.root.after(0, _sync_status_wrap)

    content = ttk.Frame(main)
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)
    content.columnconfigure(1, weight=0)
    content.rowconfigure(0, weight=1)

    left = ttk.Frame(content)
    left.grid(row=0, column=0, sticky="nsew")
    left.columnconfigure(0, weight=1)
    left.rowconfigure(0, weight=1)
    left.rowconfigure(1, weight=0)

    canvas_frame = ttk.Frame(left)
    canvas_frame.grid(row=0, column=0, sticky="nsew")

    editor.canvas = KeyboardCanvas(
        canvas_frame,
        editor=editor,
        bg=editor.bg_color,
        highlightthickness=0,
    )
    editor.canvas.pack(side=tk.LEFT, fill="both", expand=True)

    right = ttk.Frame(content, width=editor._right_panel_width)
    right.grid(row=0, column=1, sticky="ns", padx=(16, 0))
    right.pack_propagate(False)

    backdrop_row = ttk.Frame(right)
    backdrop_row.pack(fill="x", pady=(0, 10))
    ttk.Button(backdrop_row, text="Set Backdrop...", command=editor._set_backdrop).pack(
        side="left", fill="x", expand=True, padx=(0, 6)
    )
    ttk.Button(backdrop_row, text="Reset Backdrop", command=editor._reset_backdrop).pack(
        side="left", fill="x", expand=True
    )

    ttk.Label(right, text="Backdrop transparency", font=("Sans", 9)).pack(anchor="w", pady=(0, 4))
    ttk.Scale(
        right,
        from_=0,
        to=100,
        orient="horizontal",
        variable=editor.backdrop_transparency,
        command=editor._on_backdrop_transparency_changed,
    ).pack(fill="x", pady=(0, 10))

    initial = editor._last_non_black_color
    editor.color_wheel = ColorWheel(
        right,
        size=editor._wheel_size,
        initial_color=initial,
        callback=editor._on_color_change,
        release_callback=editor._on_color_release,
        show_rgb_label=False,
    )
    editor.color_wheel.pack()

    apply_row = ttk.Frame(right)
    apply_row.pack(fill="x", pady=(8, 0))
    ttk.Checkbutton(
        apply_row,
        text="Apply to all keys",
        variable=editor.apply_all_keys,
    ).pack(anchor="w")

    ttk.Checkbutton(
        apply_row,
        text="Sample tool",
        variable=editor.sample_tool_enabled,
        command=editor._on_sample_tool_toggled,
    ).pack(anchor="w", pady=(6, 0))

    btns = ttk.Frame(right)
    btns.pack(fill="x", pady=12)

    def _divider(parent: ttk.Frame, title: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 6))
        ttk.Label(row, text=title, font=("Sans", 9)).pack(side="left")
        ttk.Separator(row, orient="horizontal").pack(side="left", fill="x", expand=True, padx=(8, 0))

    _divider(btns, "Config")
    ttk.Button(btns, text="Fill All", command=editor._fill_all).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Clear All", command=editor._clear_all).pack(fill="x", pady=(0, 6))

    _divider(btns, "Setup")
    ttk.Button(btns, text="Overlay Editor", command=editor._toggle_overlay).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Keymap Calibrator", command=editor._run_calibrator).pack(fill="x", pady=(0, 6))
    ttk.Button(btns, text="Reload Keymap", command=editor._reload_keymap).pack(fill="x")

    extras = ttk.Frame(left)
    extras.grid(row=1, column=0, sticky="ew", pady=(12, 0))
    extras.rowconfigure(0, weight=1)
    extras.columnconfigure(0, weight=1, uniform="perkey_bottom")
    extras.columnconfigure(1, weight=1, uniform="perkey_bottom")

    extras_profiles = ttk.Frame(extras)
    extras_profiles.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    extras_overlay = ttk.Frame(extras)
    extras_overlay.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    extras_profiles.columnconfigure(0, weight=1)
    extras_overlay.columnconfigure(0, weight=1)

    editor._profiles_frame = ttk.LabelFrame(extras_profiles, text="Profiles", padding=10)
    editor._profiles_frame.grid(row=0, column=0, sticky="nsew")
    editor._profiles_frame.columnconfigure(1, weight=1)

    ttk.Label(editor._profiles_frame, text="Profile").grid(row=0, column=0, sticky="w")
    editor._profiles_combo = ttk.Combobox(
        editor._profiles_frame,
        textvariable=editor._profile_name_var,
        values=profiles.list_profiles(),
        width=22,
        state="readonly",
    )
    editor._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    # The default ttk Combobox popdown opens downward, which often gets clipped
    # by the bottom panel. Use a small popup list that opens upwards.
    editor._profiles_dropdown = _UpwardListboxDropdown(
        root=editor.root,
        anchor=editor._profiles_combo,
        values_provider=profiles.list_profiles,
        get_current_value=lambda: editor._profile_name_var.get(),
        set_value=lambda v: editor._profile_name_var.set(v),
        bg=getattr(editor, "bg_color", "#2b2b2b"),
        fg=getattr(editor, "fg_color", "#ffffff"),
    )

    # Intercept the default popdown.
    editor._profiles_combo.bind("<Button-1>", editor._profiles_dropdown.open)
    editor._profiles_combo.bind("<Down>", editor._profiles_dropdown.open)

    pbtns = ttk.Frame(editor._profiles_frame)
    pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    pbtns.columnconfigure(0, weight=1)
    pbtns.columnconfigure(1, weight=1)
    pbtns.columnconfigure(2, weight=1)
    pbtns.columnconfigure(3, weight=1)

    ttk.Button(pbtns, text="New", command=editor._new_profile).grid(row=0, column=0, sticky="ew", padx=(0, 3))
    ttk.Button(pbtns, text="Activate", command=editor._activate_profile).grid(row=0, column=1, sticky="ew", padx=(3, 3))
    ttk.Button(pbtns, text="Save", command=editor._save_profile).grid(row=0, column=2, sticky="ew", padx=(3, 3))
    ttk.Button(pbtns, text="Delete", command=editor._delete_profile).grid(row=0, column=3, sticky="ew", padx=(3, 0))

    ttk.Button(editor._profiles_frame, text="Set as Default", command=editor._set_default_profile).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="ew",
        pady=(8, 0),
    )

    editor.overlay_controls = OverlayControls(extras_overlay, editor=editor)
    editor.overlay_controls.grid(row=0, column=0, sticky="nsew")
    # Hidden by default (toggled by the Overlay button)
    editor.overlay_controls.grid_remove()
    editor.overlay_controls.sync_vars_from_scope()
