from __future__ import annotations

from collections.abc import Callable
import tkinter as _tk
from typing import Protocol, TypeAlias, cast

from src.gui.utils.window_geometry import compute_centered_window_geometry


BindCallback: TypeAlias = Callable[[_tk.Event], None]
AfterCallback: TypeAlias = Callable[[], None]


class _GridWidgetProtocol(Protocol):
    def grid(self, *args: object, **kwargs: object) -> object: ...


class _ConfigurableWidgetProtocol(_GridWidgetProtocol, Protocol):
    def configure(self, **kwargs: object) -> object: ...


class _BindableWidgetProtocol(_ConfigurableWidgetProtocol, Protocol):
    def bind(self, sequence: str, callback: BindCallback, add: object = None) -> object: ...


class _ContainerWidgetProtocol(_BindableWidgetProtocol, Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def winfo_width(self) -> int: ...


class _BoolVarProtocol(Protocol):
    def get(self) -> bool: ...


class _CanvasFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _BindableWidgetProtocol: ...


class _FrameFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _ContainerWidgetProtocol: ...


class _LabelFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _ConfigurableWidgetProtocol: ...


class _ButtonFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _GridWidgetProtocol: ...


class _CheckbuttonFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _GridWidgetProtocol: ...


class _BooleanVarFactoryProtocol(Protocol):
    def __call__(
        self,
        master: object | None = None,
        value: object | None = None,
        name: str | None = None,
    ) -> _BoolVarProtocol: ...


class _TkModuleProtocol(Protocol):
    Canvas: _CanvasFactoryProtocol
    BooleanVar: _BooleanVarFactoryProtocol


class _TtkModuleProtocol(Protocol):
    Frame: _FrameFactoryProtocol
    Label: _LabelFactoryProtocol
    Button: _ButtonFactoryProtocol
    Checkbutton: _CheckbuttonFactoryProtocol


class _BuildWidgetsAppProtocol(Protocol):
    bg_color: str
    canvas: _BindableWidgetProtocol
    lbl_cell: _ConfigurableWidgetProtocol
    lbl_status: _ConfigurableWidgetProtocol
    _show_backdrop_var: _BoolVarProtocol

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def bind(self, sequence: str, callback: BindCallback, add: object = None) -> object: ...

    def after(self, delay_ms: int, callback: AfterCallback) -> object: ...

    def destroy(self) -> None: ...

    def _redraw(self) -> None: ...

    def _on_click(self, event: _tk.Event) -> None: ...

    def _prev(self) -> None: ...

    def _next(self) -> None: ...

    def _assign(self) -> None: ...

    def _skip(self) -> None: ...

    def _on_show_backdrop_changed(self) -> None: ...

    def _reset_keymap_defaults(self) -> None: ...

    def _save(self) -> None: ...

    def _save_and_close(self) -> None: ...


class _WindowGeometryAppProtocol(Protocol):
    def update_idletasks(self) -> None: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...

    def winfo_reqwidth(self) -> int: ...

    def winfo_reqheight(self) -> int: ...

    def geometry(self, value: str) -> object: ...

    def minsize(self, width: int, height: int) -> object: ...


class _FinishInitAppProtocol(Protocol):
    def _load_deck_image(self) -> None: ...

    def _apply_current_probe(self) -> None: ...

    def _redraw(self) -> None: ...

    def deiconify(self) -> None: ...

    def lift(self) -> None: ...

    def after(self, delay_ms: int, callback: AfterCallback) -> object: ...


def build_widgets(
    app: _BuildWidgetsAppProtocol,
    *,
    tk: _TkModuleProtocol,
    ttk: _TtkModuleProtocol,
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

    def _redraw_from_event(_event: _tk.Event) -> None:
        app._redraw()

    app.canvas.bind("<Configure>", _redraw_from_event)
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

    def _sync_side_wrap() -> None:
        try:
            width = int(side.winfo_width())
            app.lbl_status.configure(wraplength=max(220, width - 8))
        except wrap_sync_errors:
            return

    def _sync_side_wrap_from_event(_event: _tk.Event) -> None:
        _sync_side_wrap()

    try:
        side.bind("<Configure>", _sync_side_wrap_from_event, add=True)
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

    def _assign_from_event(_event: _tk.Event) -> None:
        app._assign()

    def _next_from_event(_event: _tk.Event) -> None:
        app._next()

    def _prev_from_event(_event: _tk.Event) -> None:
        app._prev()

    def _destroy_from_event(_event: _tk.Event) -> None:
        app.destroy()

    app.bind("<Return>", _assign_from_event)
    app.bind("<KP_Enter>", _assign_from_event)
    app.bind("<Right>", _next_from_event)
    app.bind("<Left>", _prev_from_event)
    app.bind("<Escape>", _destroy_from_event)


def apply_window_geometry(app: _WindowGeometryAppProtocol) -> None:
    app.update_idletasks()
    screen_width = int(app.winfo_screenwidth())
    screen_height = int(app.winfo_screenheight())
    max_width = int(screen_width * 0.95)
    max_height = int(screen_height * 0.95)
    requested_width = int(app.winfo_reqwidth())
    requested_height = int(app.winfo_reqheight())

    app.geometry(
        compute_centered_window_geometry(
            cast(_tk.Tk, app),
            content_height_px=requested_height,
            content_width_px=requested_width,
            footer_height_px=0,
            chrome_padding_px=32,
            default_w=1400,
            default_h=860,
            screen_ratio_cap=0.95,
        )
    )
    app.minsize(min(max(requested_width, 1100), max_width), min(max(requested_height + 32, 650), max_height))


def finish_init(app: _FinishInitAppProtocol, *, tk_runtime_errors: tuple[type[BaseException], ...]) -> None:
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
