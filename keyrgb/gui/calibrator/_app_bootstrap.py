from __future__ import annotations

import tkinter as _tk
from collections.abc import Callable
from typing import Any, Protocol, TypeAlias, cast

from keyrgb.gui.theme import metrics as theme_metrics
from keyrgb.gui.theme.focus import schedule_initial_focus
from keyrgb.gui.utils.window_geometry import compute_centered_window_geometry
from keyrgb.gui.utils.window_state import WindowGeometryTracker

CALIBRATOR_WINDOW_ID = "calibrator"
CALIBRATOR_MIN_WIDTH_PX = 1100
CALIBRATOR_MIN_HEIGHT_PX = 650
CALIBRATOR_SCREEN_RATIO_CAP = 0.95

BindCallback: TypeAlias = Callable[[_tk.Event], None]
AfterCallback: TypeAlias = Callable[[], None]


class _GridWidgetProtocol(Protocol):
    def grid(self, *args: object, **kwargs: object) -> object: ...


class _ConfigurableWidgetProtocol(_GridWidgetProtocol, Protocol):
    def configure(self, *args: object, **kwargs: object) -> object: ...


class _BindableWidgetProtocol(_ConfigurableWidgetProtocol, Protocol):
    def bind(self, sequence: str, callback: BindCallback, add: object = None) -> object: ...


class _ContainerWidgetProtocol(_BindableWidgetProtocol, Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> object: ...

    def winfo_width(self) -> int: ...


class _BoolVarProtocol(Protocol):
    def get(self) -> bool: ...


class _CanvasFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _BindableWidgetProtocol: ...


class _FrameFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _ContainerWidgetProtocol: ...


class _LabelFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _ConfigurableWidgetProtocol: ...


class _ButtonFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _GridWidgetProtocol: ...


class _CheckbuttonFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _GridWidgetProtocol: ...


class _BooleanVarFactoryProtocol(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _BoolVarProtocol: ...


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

    def _on_close(self) -> None: ...


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
    tk: object,
    ttk: object,
    tk_runtime_errors: tuple[type[BaseException], ...],
    wrap_sync_errors: tuple[type[BaseException], ...],
) -> None:
    tk_mod = cast(_TkModuleProtocol, tk)
    ttk_mod = cast(_TtkModuleProtocol, ttk)
    window = cast(_tk.Tk, app)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)

    root = ttk_mod.Frame(app, padding=theme_metrics.OUTER_PADDING)
    root.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=0)
    root.rowconfigure(0, weight=1)

    app.canvas = tk_mod.Canvas(root, background=app.bg_color, highlightthickness=0)
    app.canvas.grid(row=0, column=0, sticky="nsew")

    def _redraw_from_event(_event: _tk.Event) -> None:
        app._redraw()

    app.canvas.bind("<Configure>", _redraw_from_event)
    app.canvas.bind("<Button-1>", app._on_click)

    side = ttk_mod.Frame(root, padding=0)
    side.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
    side.columnconfigure(0, weight=1)

    ttk_mod.Label(side, text="Keymap Calibrator", style=theme_metrics.TITLE_LABEL_STYLE, anchor="w").grid(
        row=0, column=0, sticky="ew", pady=(0, 10)
    )

    app.lbl_cell = ttk_mod.Label(side, text="", style=theme_metrics.BODY_LABEL_STYLE, anchor="w")
    app.lbl_cell.grid(row=1, column=0, sticky="ew", pady=(0, 8))

    app.lbl_status = ttk_mod.Label(
        side,
        text=(
            "Step 1: look at the lit key on the keyboard\n"
            "Step 2: click that key on the image\n"
            "Step 3: click 'Assign selected key' (or press Enter)"
        ),
        style=theme_metrics.STATUS_LABEL_STYLE,
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
    window.after(0, _sync_side_wrap)

    btns = ttk_mod.Frame(side)
    btns.grid(row=3, column=0, sticky="ew")
    btns.columnconfigure(0, weight=1)
    btns.columnconfigure(1, weight=1)

    ttk_mod.Button(btns, text="Prev", command=app._prev).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk_mod.Button(btns, text="Next", command=app._next).grid(row=0, column=1, sticky="ew")

    assign_btn = ttk_mod.Button(
        side,
        text="Assign selected key",
        command=app._assign,
        style=theme_metrics.PRIMARY_BUTTON_STYLE,
    )
    assign_btn.grid(row=4, column=0, sticky="ew", pady=(10, 0))
    ttk_mod.Button(side, text="Skip (nothing lit)", command=app._skip).grid(row=5, column=0, sticky="ew", pady=(6, 0))

    app._show_backdrop_var = tk_mod.BooleanVar(value=True)
    ttk_mod.Checkbutton(
        side,
        text="Show backdrop",
        variable=app._show_backdrop_var,
        command=app._on_show_backdrop_changed,
    ).grid(row=6, column=0, sticky="ew", pady=(18, 0))

    ttk_mod.Button(side, text="Reset Keymap Defaults", command=app._reset_keymap_defaults).grid(
        row=7, column=0, sticky="ew", pady=(18, 0)
    )
    ttk_mod.Button(side, text="Save", command=app._save).grid(row=8, column=0, sticky="ew", pady=(18, 0))
    ttk_mod.Button(side, text="Save && Close", command=app._save_and_close).grid(
        row=9, column=0, sticky="ew", pady=(6, 0)
    )

    def _assign_from_event(_event: _tk.Event) -> None:
        app._assign()

    def _next_from_event(_event: _tk.Event) -> None:
        app._next()

    def _prev_from_event(_event: _tk.Event) -> None:
        app._prev()

    def _close_from_event(_event: _tk.Event) -> None:
        app._on_close()

    window.bind("<Return>", _assign_from_event)
    window.bind("<KP_Enter>", _assign_from_event)
    window.bind("<Right>", _next_from_event)
    window.bind("<Left>", _prev_from_event)
    window.bind("<Escape>", _close_from_event)

    # Intentional non-forcing initial focus: Assign is always present and
    # enabled, and matches the core probe loop (Step 3). The helper schedules
    # via `after`, never grabs, and never steals an already-focused child.
    schedule_initial_focus(cast(Any, window), cast(Any, assign_btn))


def apply_window_geometry(app: _WindowGeometryAppProtocol) -> bool:
    """Apply the initial calibrator geometry.

    Returns ``True`` when a stored geometry was restored (the centered
    fallback is skipped so it cannot overwrite it); the resize floor is
    still re-asserted in that case. Returns ``False`` when the exact
    legacy centered fallback was applied.
    """
    app.update_idletasks()
    screen_width = int(app.winfo_screenwidth())
    screen_height = int(app.winfo_screenheight())
    max_width = int(screen_width * CALIBRATOR_SCREEN_RATIO_CAP)
    max_height = int(screen_height * CALIBRATOR_SCREEN_RATIO_CAP)
    requested_width = int(app.winfo_reqwidth())
    requested_height = int(app.winfo_reqheight())
    min_width = min(max(requested_width, CALIBRATOR_MIN_WIDTH_PX), max_width)
    min_height = min(max(requested_height + 32, CALIBRATOR_MIN_HEIGHT_PX), max_height)

    tracker = WindowGeometryTracker(
        app,
        CALIBRATOR_WINDOW_ID,
        min_width,
        min_height,
        screen_ratio_cap=CALIBRATOR_SCREEN_RATIO_CAP,
    )
    vars(app)["_window_geometry_tracker"] = tracker
    if tracker.restore():
        # The tracker clamps restored size to the content-derived resize floor;
        # re-assert that floor without moving the restored window.
        app.minsize(min_width, min_height)
        return True

    app.geometry(
        compute_centered_window_geometry(
            cast(_tk.Tk, app),
            content_height_px=requested_height,
            content_width_px=requested_width,
            footer_height_px=0,
            chrome_padding_px=32,
            default_w=1400,
            default_h=860,
            screen_ratio_cap=CALIBRATOR_SCREEN_RATIO_CAP,
        )
    )
    app.minsize(min_width, min_height)
    return False


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
        # Start <Configure> persistence only after the withdraw/deiconify
        # startup callbacks so restored geometry cannot be overwritten.
        tracker = vars(app).get("_window_geometry_tracker")
        start_tracking = getattr(tracker, "start_tracking", None)
        if callable(start_tracking):
            app.after(50, start_tracking)

    app.after(0, _finish)
