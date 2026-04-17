from __future__ import annotations

from typing import Protocol, cast


_UNSUPPORTED_BACKEND_TEXT = (
    "RGB color control is not available with the currently selected backend.\n\n"
    "Reactive typing can still run, but manual highlight color won’t be applied to the keyboard on "
    "brightness-only backends (common with sysfs kbd_backlight)."
)


class _ReactiveColorConfigLike(Protocol):
    reactive_color: tuple[int, int, int]


class _ManualToggleCallback(Protocol):
    def __call__(self) -> None: ...


class _ScaleChangeCallback(Protocol):
    def __call__(self, value: str | float) -> None: ...


class _EventCallback(Protocol):
    def __call__(self, _event: object | None = None) -> None: ...


class _ColorChangeCallback(Protocol):
    def __call__(
        self,
        red: int,
        green: int,
        blue: int,
        *,
        source: str | None = None,
        brightness_percent: float | None = None,
    ) -> None: ...


class _BoolVarLike(Protocol):
    def get(self) -> object: ...

    def set(self, value: bool) -> None: ...


class _DoubleVarLike(Protocol):
    def get(self) -> object: ...

    def set(self, value: float) -> None: ...


class _PackableWidget(Protocol):
    def pack(self, **kwargs: object) -> None: ...


class _GridWidget(Protocol):
    def grid(self, **kwargs: object) -> None: ...


class _ConfigurableWidget(Protocol):
    def config(self, **kwargs: object) -> None: ...

    def configure(self, **kwargs: object) -> None: ...


class _BindableWidget(Protocol):
    def bind(self, sequence: str, callback: _EventCallback) -> None: ...


class _ColumnConfigurableWidget(Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...


class _LabelWidget(_PackableWidget, _GridWidget, _ConfigurableWidget, Protocol):
    pass


class _CheckbuttonWidget(_PackableWidget, _ConfigurableWidget, Protocol):
    pass


class _SeparatorWidget(_PackableWidget, Protocol):
    pass


class _FrameWidget(_PackableWidget, _ColumnConfigurableWidget, Protocol):
    pass


class _ScaleWidget(_GridWidget, _BindableWidget, Protocol):
    pass


class _BoolVarFactory(Protocol):
    def __call__(self, *, value: bool = False) -> _BoolVarLike: ...


class _DoubleVarFactory(Protocol):
    def __call__(self, *, value: float = 0.0) -> _DoubleVarLike: ...


class _CheckbuttonFactory(Protocol):
    def __call__(
        self,
        parent: object | None = None,
        *,
        text: str,
        variable: _BoolVarLike,
        command: _ManualToggleCallback,
        **kwargs: object,
    ) -> _CheckbuttonWidget: ...


class _LabelFactory(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _LabelWidget: ...


class _SeparatorFactory(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _SeparatorWidget: ...


class _FrameFactory(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _FrameWidget: ...


class _ScaleFactory(Protocol):
    def __call__(
        self,
        parent: object | None = None,
        *,
        command: _ScaleChangeCallback,
        **kwargs: object,
    ) -> _ScaleWidget: ...


class _TkModuleLike(Protocol):
    BooleanVar: _BoolVarFactory
    DoubleVar: _DoubleVarFactory


class _TtkModuleLike(Protocol):
    Checkbutton: _CheckbuttonFactory
    Label: _LabelFactory
    Separator: _SeparatorFactory
    Frame: _FrameFactory
    Scale: _ScaleFactory


class _ColorWheelLike(_PackableWidget, Protocol):
    def set_brightness_percent(self, pct: int) -> None: ...


class _ColorWheelFactory(Protocol):
    def __call__(
        self,
        parent: object | None = None,
        *,
        size: int,
        initial_color: tuple[int, int, int],
        callback: _ColorChangeCallback,
        release_callback: _ColorChangeCallback,
        show_brightness_slider: bool,
    ) -> _ColorWheelLike: ...


class _ReactiveColorWindowState(Protocol):
    config: _ReactiveColorConfigLike
    _color_supported: bool
    _wrap_labels: list[object]
    _use_manual_var: _BoolVarLike
    _manual_check: _CheckbuttonWidget
    color_wheel: _ColorWheelLike | None
    _reactive_brightness_var: _DoubleVarLike
    _reactive_brightness_scale: _ScaleWidget
    _reactive_brightness_label: _LabelWidget
    _reactive_trail_var: _DoubleVarLike
    _reactive_trail_scale: _ScaleWidget
    _reactive_trail_label: _LabelWidget
    status_label: _LabelWidget

    def _on_toggle_manual(self) -> None: ...

    def _on_color_change(
        self,
        red: int,
        green: int,
        blue: int,
        *,
        source: str | None = None,
        brightness_percent: float | None = None,
    ) -> None: ...

    def _on_color_release(
        self,
        red: int,
        green: int,
        blue: int,
        *,
        source: str | None = None,
        brightness_percent: float | None = None,
    ) -> None: ...

    def _on_reactive_brightness_change(self, value: str | float) -> None: ...

    def _on_reactive_brightness_release(self, _event: object | None = None) -> None: ...

    def _sync_reactive_brightness_widgets(self) -> None: ...

    def _sync_color_wheel_brightness(self) -> None: ...

    def _on_reactive_trail_change(self, value: str | float) -> None: ...

    def _on_reactive_trail_release(self, _event: object | None = None) -> None: ...

    def _sync_reactive_trail_widgets(self) -> None: ...


def build_reactive_window_ui(
    gui: object,
    main: object,
    *,
    tk_module: _TkModuleLike,
    ttk_module: _TtkModuleLike,
    color_wheel_cls: _ColorWheelFactory,
    wrap_sync_errors: tuple[type[BaseException], ...],
    tk_error: type[BaseException],
) -> None:
    gui_state = cast(_ReactiveColorWindowState, gui)

    gui_state._use_manual_var = tk_module.BooleanVar(
        value=bool(getattr(gui_state.config, "reactive_use_manual_color", False))
    )
    gui_state._manual_check = ttk_module.Checkbutton(
        main,
        text="Use manual color for reactive typing",
        variable=gui_state._use_manual_var,
        command=gui_state._on_toggle_manual,
    )
    gui_state._manual_check.pack(anchor="w", pady=(0, 10))

    if not gui_state._color_supported:
        try:
            gui_state._use_manual_var.set(False)
        except tk_error:
            pass
        try:
            gui_state._manual_check.configure(state="disabled")
        except tk_error:
            pass
        msg = ttk_module.Label(
            main,
            text=_UNSUPPORTED_BACKEND_TEXT,
            font=("Sans", 9),
            justify="left",
            wraplength=520,
        )
        msg.pack(pady=(6, 10), fill="x")
        gui_state._wrap_labels.append(msg)

    if gui_state._color_supported:
        initial = gui_state.config.reactive_color
        color_wheel = color_wheel_cls(
            main,
            size=350,
            initial_color=tuple(initial),
            callback=gui_state._on_color_change,
            release_callback=gui_state._on_color_release,
            show_brightness_slider=False,
        )
        color_wheel.pack()
        gui_state.color_wheel = color_wheel
    else:
        gui_state.color_wheel = None

    ttk_module.Separator(main, orient="horizontal").pack(fill="x", pady=(18, 12))

    gui_state._reactive_brightness_var = tk_module.DoubleVar(value=100.0)
    brightness_frame = ttk_module.Frame(main)
    brightness_frame.pack(fill="x", padx=10)
    try:
        brightness_frame.columnconfigure(1, weight=1)
    except wrap_sync_errors:
        pass

    ttk_module.Label(brightness_frame, text="Reactive typing brightness:").grid(
        row=0,
        column=0,
        sticky="w",
        padx=(0, 10),
    )

    gui_state._reactive_brightness_scale = ttk_module.Scale(
        brightness_frame,
        from_=0,
        to=100,
        orient="horizontal",
        variable=gui_state._reactive_brightness_var,
        command=gui_state._on_reactive_brightness_change,
    )
    gui_state._reactive_brightness_scale.grid(row=0, column=1, sticky="ew")

    gui_state._reactive_brightness_label = ttk_module.Label(brightness_frame, text="100%")
    gui_state._reactive_brightness_label.configure(width=5)
    gui_state._reactive_brightness_label.grid(row=0, column=2, sticky="e", padx=(10, 5))

    try:
        gui_state._reactive_brightness_scale.bind("<ButtonRelease-1>", gui_state._on_reactive_brightness_release)
    except tk_error:
        pass

    gui_state._sync_reactive_brightness_widgets()
    gui_state._sync_color_wheel_brightness()

    ttk_module.Separator(main, orient="horizontal").pack(fill="x", pady=(18, 12))

    gui_state._reactive_trail_var = tk_module.DoubleVar(value=50.0)
    trail_frame = ttk_module.Frame(main)
    trail_frame.pack(fill="x", padx=10)
    try:
        trail_frame.columnconfigure(1, weight=1)
    except wrap_sync_errors:
        pass

    ttk_module.Label(trail_frame, text="Wave thickness:").grid(row=0, column=0, sticky="w", padx=(0, 10))

    gui_state._reactive_trail_scale = ttk_module.Scale(
        trail_frame,
        from_=1,
        to=100,
        orient="horizontal",
        variable=gui_state._reactive_trail_var,
        command=gui_state._on_reactive_trail_change,
    )
    gui_state._reactive_trail_scale.grid(row=0, column=1, sticky="ew")

    gui_state._reactive_trail_label = ttk_module.Label(trail_frame, text="50%")
    gui_state._reactive_trail_label.configure(width=5)
    gui_state._reactive_trail_label.grid(row=0, column=2, sticky="e", padx=(10, 5))

    try:
        gui_state._reactive_trail_scale.bind("<ButtonRelease-1>", gui_state._on_reactive_trail_release)
    except tk_error:
        pass

    gui_state._sync_reactive_trail_widgets()

    gui_state.status_label = ttk_module.Label(main, text="", font=("Sans", 9))
    gui_state.status_label.pack(pady=(10, 0))
