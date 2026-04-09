from __future__ import annotations

from typing import Any


def build_widgets(
    app: Any,
    *,
    tk: Any,
    ttk: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
    wrap_sync_errors: tuple[type[BaseException], ...],
) -> None:
    app.columnconfigure(0, weight=1)
    app.rowconfigure(0, weight=1)

    root = ttk.Frame(app, padding=16)
    root.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=0)
    root.rowconfigure(0, weight=1)

    app.canvas = tk.Canvas(root, background=app.bg_color, highlightthickness=0)
    app.canvas.grid(row=0, column=0, sticky="nsew")
    app.canvas.bind("<Configure>", lambda _event: app._redraw())
    app.canvas.bind("<Button-1>", app._on_click)

    side = ttk.Frame(root, padding=0)
    side.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
    side.columnconfigure(0, weight=1)

    ttk.Label(side, text="Keymap Calibrator", font=("Sans", 14, "bold"), anchor="w").grid(
        row=0, column=0, sticky="ew", pady=(0, 10)
    )

    app.lbl_cell = ttk.Label(side, text="", font=("Sans", 9), anchor="w")
    app.lbl_cell.grid(row=1, column=0, sticky="ew", pady=(0, 8))

    app.lbl_status = ttk.Label(
        side,
        text=(
            "Step 1: look at the lit key on the keyboard\n"
            "Step 2: click that key on the image\n"
            "Step 3: click 'Assign selected key' (or press Enter)"
        ),
        anchor="w",
        justify="left",
    )
    app.lbl_status.grid(row=2, column=0, sticky="ew", pady=(0, 12))

    def _sync_side_wrap(_event=None) -> None:
        try:
            width = int(side.winfo_width())
            app.lbl_status.configure(wraplength=max(220, width - 8))
        except wrap_sync_errors:
            return

    try:
        side.bind("<Configure>", _sync_side_wrap, add=True)
    except tk_runtime_errors:
        pass
    app.after(0, _sync_side_wrap)

    btns = ttk.Frame(side)
    btns.grid(row=3, column=0, sticky="ew")
    btns.columnconfigure(0, weight=1)
    btns.columnconfigure(1, weight=1)

    ttk.Button(btns, text="Prev", command=app._prev).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(btns, text="Next", command=app._next).grid(row=0, column=1, sticky="ew")

    ttk.Button(side, text="Assign selected key", command=app._assign).grid(row=4, column=0, sticky="ew", pady=(10, 0))
    ttk.Button(side, text="Skip (nothing lit)", command=app._skip).grid(row=5, column=0, sticky="ew", pady=(6, 0))

    app._show_backdrop_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        side,
        text="Show backdrop",
        variable=app._show_backdrop_var,
        command=app._on_show_backdrop_changed,
    ).grid(row=6, column=0, sticky="ew", pady=(18, 0))

    ttk.Button(side, text="Reset Keymap Defaults", command=app._reset_keymap_defaults).grid(
        row=7, column=0, sticky="ew", pady=(18, 0)
    )
    ttk.Button(side, text="Save", command=app._save).grid(row=8, column=0, sticky="ew", pady=(18, 0))
    ttk.Button(side, text="Save && Close", command=app._save_and_close).grid(row=9, column=0, sticky="ew", pady=(6, 0))

    app.bind("<Return>", lambda _event: app._assign())
    app.bind("<KP_Enter>", lambda _event: app._assign())
    app.bind("<Right>", lambda _event: app._next())
    app.bind("<Left>", lambda _event: app._prev())
    app.bind("<Escape>", lambda _event: app.destroy())


def apply_window_geometry(app: Any) -> None:
    app.update_idletasks()
    screen_width = int(app.winfo_screenwidth())
    screen_height = int(app.winfo_screenheight())
    width = min(1400, int(screen_width * 0.95))
    height = min(860, int(screen_height * 0.95))
    app.geometry(f"{width}x{height}")
    app.minsize(min(1100, width), min(650, height))


def finish_init(app: Any, *, tk_runtime_errors: tuple[type[BaseException], ...]) -> None:
    def _finish() -> None:
        app._load_deck_image()
        app._apply_current_probe()
        app._redraw()
        try:
            app.deiconify()
            app.lift()
        except tk_runtime_errors:
            pass

    app.after(0, _finish)
