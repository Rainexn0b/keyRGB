from __future__ import annotations

from typing import Protocol, cast


Color = tuple[int, int, int]

_UNSUPPORTED_BACKEND_TEXT = (
    "RGB color control is not available with the currently selected backend.\n\n"
    "This usually means the sysfs LED driver only exposes brightness (no writable RGB attribute).\n"
    "You can still adjust brightness from the tray, or switch to a backend that supports RGB color."
)


class _EventCallback(Protocol):
    def __call__(self, _event: object | None = None) -> None: ...


class _ActionCallback(Protocol):
    def __call__(self) -> None: ...


class _ColorChangeCallback(Protocol):
    def __call__(self, red: int, green: int, blue: int) -> None: ...


class _PackableWidget(Protocol):
    def pack(self, **kwargs: object) -> None: ...


class _GridWidget(Protocol):
    def grid(self, **kwargs: object) -> None: ...


class _ConfigurableWidget(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _WidthWidget(Protocol):
    def winfo_width(self) -> int: ...


class _BindableWidget(Protocol):
    def bind(self, sequence: str, callback: _EventCallback) -> None: ...


class _ColumnConfigurableWidget(Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...


class _WrapLabelWidget(_ConfigurableWidget, Protocol):
    pass


class _FrameWidget(_PackableWidget, _BindableWidget, _WidthWidget, _ColumnConfigurableWidget, Protocol):
    pass


class _LabelWidget(_PackableWidget, _WrapLabelWidget, Protocol):
    pass


class _ButtonWidget(_GridWidget, _ConfigurableWidget, Protocol):
    pass


class _ColorWheelWidget(_PackableWidget, Protocol):
    def get_color(self) -> Color: ...


class _RootProtocol(Protocol):
    def after(self, delay_ms: int, callback: _EventCallback) -> object: ...


class _FrameFactory(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _FrameWidget: ...


class _LabelFactory(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _LabelWidget: ...


class _ButtonFactory(Protocol):
    def __call__(
        self,
        parent: object | None = None,
        *,
        text: str,
        command: _ActionCallback,
        **kwargs: object,
    ) -> _ButtonWidget: ...


class _ColorWheelFactory(Protocol):
    def __call__(
        self,
        parent: object | None = None,
        *,
        size: int,
        initial_color: Color,
        callback: _ColorChangeCallback,
        release_callback: _ColorChangeCallback,
    ) -> _ColorWheelWidget: ...


class _TtkModuleProtocol(Protocol):
    Frame: _FrameFactory
    Label: _LabelFactory
    Button: _ButtonFactory


class _UniformColorWindowState(Protocol):
    root: _RootProtocol
    _target_label: object
    _color_supported: bool
    _main_frame: _FrameWidget
    _wrap_labels: list[_WrapLabelWidget]
    color_wheel: _ColorWheelWidget | None
    status_label: _LabelWidget

    def _initial_color(self) -> Color: ...

    def _on_color_change(self, red: int, green: int, blue: int) -> None: ...

    def _on_color_release(self, red: int, green: int, blue: int) -> None: ...

    def _on_apply(self) -> None: ...

    def _on_close(self) -> None: ...


def build_uniform_window_ui(
    gui: object,
    *,
    ttk_module: _TtkModuleProtocol,
    color_wheel_cls: _ColorWheelFactory,
    wrap_sync_errors: tuple[type[BaseException], ...],
    tk_widget_state_errors: tuple[type[BaseException], ...],
) -> None:
    gui_state = cast(_UniformColorWindowState, gui)

    main_frame = ttk_module.Frame(gui_state.root, padding=20)
    main_frame.pack(fill="both", expand=True)
    gui_state._main_frame = main_frame
    gui_state._wrap_labels = []

    ttk_module.Label(
        main_frame,
        text=f"Select Uniform {gui_state._target_label} Color",
        font=("Sans", 14, "bold"),
    ).pack(pady=(0, 10))

    def _sync_wrap(_event: object | None = None) -> None:
        try:
            width = int(main_frame.winfo_width())
            if width <= 1:
                return
            wrap = max(220, width - 24)
            for label in gui_state._wrap_labels:
                label.configure(wraplength=wrap)
        except wrap_sync_errors:
            return

    main_frame.bind("<Configure>", _sync_wrap)
    gui_state.root.after(0, _sync_wrap)

    if not gui_state._color_supported:
        msg = ttk_module.Label(
            main_frame,
            text=_UNSUPPORTED_BACKEND_TEXT,
            font=("Sans", 9),
            justify="left",
            wraplength=420,
        )
        msg.pack(pady=(10, 16), fill="x")
        gui_state._wrap_labels.append(msg)
        gui_state.color_wheel = None
    else:
        gui_state.color_wheel = color_wheel_cls(
            main_frame,
            size=350,
            initial_color=gui_state._initial_color(),
            callback=gui_state._on_color_change,
            release_callback=gui_state._on_color_release,
        )
        gui_state.color_wheel.pack()

    button_frame = ttk_module.Frame(main_frame)
    button_frame.pack(pady=20, fill="x")
    try:
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
    except wrap_sync_errors:
        pass

    apply_btn = ttk_module.Button(button_frame, text="Apply", command=gui_state._on_apply)
    if not gui_state._color_supported:
        try:
            apply_btn.configure(state="disabled")
        except tk_widget_state_errors:
            pass
    apply_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    close_btn = ttk_module.Button(button_frame, text="Close", command=gui_state._on_close)
    close_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    gui_state.status_label = ttk_module.Label(main_frame, text="", font=("Sans", 9))
    gui_state.status_label.pack()
