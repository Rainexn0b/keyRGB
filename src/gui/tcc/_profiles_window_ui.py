from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class _TkRootProtocol(Protocol):
    def title(self, value: str) -> None: ...

    def minsize(self, width: int, height: int) -> None: ...

    def resizable(self, width: bool, height: bool) -> None: ...

    def after(self, delay_ms: int, callback: Callable[..., None]) -> None: ...

    def destroy(self) -> None: ...


class _PackWidgetProtocol(Protocol):
    def pack(self, **kwargs: object) -> None: ...


class _GridWidgetProtocol(Protocol):
    def grid(self, **kwargs: object) -> None: ...


class _ConfigurableWidgetProtocol(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _BindableWidgetProtocol(Protocol):
    def bind(self, sequence: str, callback: Callable[..., None]) -> None: ...


class _ColumnConfigurableWidgetProtocol(Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...


class _WidthWidgetProtocol(Protocol):
    def winfo_width(self) -> int: ...


class _FrameWidgetProtocol(
    _PackWidgetProtocol,
    _BindableWidgetProtocol,
    _ColumnConfigurableWidgetProtocol,
    _WidthWidgetProtocol,
    Protocol,
):
    pass


class _LabelWidgetProtocol(_PackWidgetProtocol, _ConfigurableWidgetProtocol, Protocol):
    pass


class _ButtonWidgetProtocol(_GridWidgetProtocol, _ConfigurableWidgetProtocol, Protocol):
    pass


class _ListboxWidgetProtocol(
    _PackWidgetProtocol,
    _BindableWidgetProtocol,
    _ConfigurableWidgetProtocol,
    Protocol,
):
    def yview(self, *args: object) -> object: ...


class _ScrollbarWidgetProtocol(_PackWidgetProtocol, Protocol):
    def set(self, *args: object) -> None: ...


class _RootFactoryProtocol(Protocol):
    def __call__(self) -> _TkRootProtocol: ...


class _ListboxFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _ListboxWidgetProtocol: ...


class _FrameFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _FrameWidgetProtocol: ...


class _LabelFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _LabelWidgetProtocol: ...


class _ButtonFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _ButtonWidgetProtocol: ...


class _ScrollbarFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _ScrollbarWidgetProtocol: ...


class _TkModuleProtocol(Protocol):
    Tk: _RootFactoryProtocol
    Listbox: _ListboxFactoryProtocol


class _TtkModuleProtocol(Protocol):
    Frame: _FrameFactoryProtocol
    LabelFrame: _FrameFactoryProtocol
    Label: _LabelFactoryProtocol
    Button: _ButtonFactoryProtocol
    Scrollbar: _ScrollbarFactoryProtocol


class _ProfilesWindowHostProtocol(Protocol):
    root: _TkRootProtocol
    _main_frame: _FrameWidgetProtocol
    _wrap_labels: list[_ConfigurableWidgetProtocol]
    listbox: _ListboxWidgetProtocol
    profile_desc: _LabelWidgetProtocol
    btn_activate: _ButtonWidgetProtocol
    btn_refresh: _ButtonWidgetProtocol
    btn_close: _ButtonWidgetProtocol
    btn_new: _ButtonWidgetProtocol
    btn_duplicate: _ButtonWidgetProtocol
    btn_rename: _ButtonWidgetProtocol
    btn_edit: _ButtonWidgetProtocol
    btn_delete: _ButtonWidgetProtocol
    status: _LabelWidgetProtocol


def build_profiles_window(
    host: object,
    *,
    tk_module: object,
    ttk_module: object,
    apply_window_icon: Callable[[object], None],
    apply_theme: Callable[[object], None],
    wrap_sync_errors: tuple[type[BaseException], ...],
    on_select: Callable[[object | None], None],
    on_activate: Callable[[], None],
    on_refresh: Callable[[], None],
    on_new: Callable[[], None],
    on_duplicate: Callable[[], None],
    on_rename: Callable[[], None],
    on_edit: Callable[[], None],
    on_delete: Callable[[], None],
) -> None:
    host_window = cast(_ProfilesWindowHostProtocol, host)
    tk_api = cast(_TkModuleProtocol, tk_module)
    ttk_api = cast(_TtkModuleProtocol, ttk_module)

    host_window.root = tk_api.Tk()
    host_window.root.title("KeyRGB - Power Profiles")
    apply_window_icon(host_window.root)
    host_window.root.minsize(620, 460)
    host_window.root.resizable(True, True)

    apply_theme(host_window.root)

    main = ttk_api.Frame(host_window.root, padding=16)
    main.pack(fill="both", expand=True)
    main.columnconfigure(0, weight=1)
    host_window._main_frame = main
    wrap_labels: list[_ConfigurableWidgetProtocol] = []
    host_window._wrap_labels = wrap_labels

    title = ttk_api.Label(main, text="Power Profiles (TCC)", font=("Sans", 14, "bold"))
    title.pack(anchor="w", pady=(0, 8))

    desc = ttk_api.Label(
        main,
        text=(
            "These profiles are provided by the TUXEDO Control Center daemon (tccd).\n"
            "Activation here is temporary (like the TCC tray behavior)."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=640,
    )
    desc.pack(anchor="w", pady=(0, 12))
    wrap_labels.append(desc)

    def _sync_wrap(_event=None) -> None:
        try:
            width = int(main.winfo_width())
            if width <= 1:
                return
            wrap = max(240, width - 24)
            for label in wrap_labels:
                label.configure(wraplength=wrap)
        except wrap_sync_errors:
            return

    main.bind("<Configure>", _sync_wrap)
    host_window.root.after(0, _sync_wrap)

    list_frame = ttk_api.Frame(main)
    list_frame.pack(fill="both", expand=True)

    host_window.listbox = tk_api.Listbox(
        list_frame,
        height=9,
        activestyle="dotbox",
        exportselection=False,
    )
    host_window.listbox.pack(side="left", fill="both", expand=True)
    host_window.listbox.bind("<<ListboxSelect>>", on_select)

    scrollbar = ttk_api.Scrollbar(list_frame, orient="vertical", command=host_window.listbox.yview)
    scrollbar.pack(side="right", fill="y")
    host_window.listbox.configure(yscrollcommand=scrollbar.set)

    details_frame = ttk_api.LabelFrame(main, text="Selected Profile", padding=12)
    details_frame.pack(fill="x", pady=(10, 0))

    host_window.profile_desc = ttk_api.Label(
        details_frame,
        text="",
        font=("Sans", 9),
        justify="left",
        wraplength=640,
    )
    host_window.profile_desc.pack(fill="x", anchor="w")
    wrap_labels.append(host_window.profile_desc)

    btn_row_top = ttk_api.Frame(main)
    btn_row_top.pack(fill="x", pady=(16, 0))
    btn_row_top.columnconfigure(0, weight=3)
    btn_row_top.columnconfigure(1, weight=2)
    btn_row_top.columnconfigure(2, weight=2)

    host_window.btn_activate = ttk_api.Button(btn_row_top, text="Activate Temporarily", command=on_activate)
    host_window.btn_activate.grid(row=0, column=0, sticky="ew")

    host_window.btn_refresh = ttk_api.Button(btn_row_top, text="Refresh", command=on_refresh)
    host_window.btn_refresh.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    host_window.btn_close = ttk_api.Button(btn_row_top, text="Close", command=host_window.root.destroy)
    host_window.btn_close.grid(row=0, column=2, sticky="ew", padx=(8, 0))

    btn_row_bottom = ttk_api.Frame(main)
    btn_row_bottom.pack(fill="x", pady=(8, 0))
    for column in range(5):
        btn_row_bottom.columnconfigure(column, weight=1)

    host_window.btn_new = ttk_api.Button(btn_row_bottom, text="New…", command=on_new)
    host_window.btn_new.grid(row=0, column=0, sticky="ew")

    host_window.btn_duplicate = ttk_api.Button(btn_row_bottom, text="Duplicate…", command=on_duplicate)
    host_window.btn_duplicate.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    host_window.btn_rename = ttk_api.Button(btn_row_bottom, text="Rename…", command=on_rename)
    host_window.btn_rename.grid(row=0, column=2, sticky="ew", padx=(8, 0))

    host_window.btn_edit = ttk_api.Button(btn_row_bottom, text="Edit…", command=on_edit)
    host_window.btn_edit.grid(row=0, column=3, sticky="ew", padx=(8, 0))

    host_window.btn_delete = ttk_api.Button(btn_row_bottom, text="Delete", command=on_delete)
    host_window.btn_delete.grid(row=0, column=4, sticky="ew", padx=(8, 0))

    host_window.status = ttk_api.Label(main, text="", font=("Sans", 9), justify="left", wraplength=640)
    host_window.status.pack(fill="x", anchor="w", pady=(8, 0))
    wrap_labels.append(host_window.status)
