from __future__ import annotations

import logging
from collections.abc import Callable
from types import TracebackType
from typing import Protocol, TypeAlias, cast


_BACKEND_CAPABILITY_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_DESCRIPTION_TEXT = (
    "Sets a manual highlight color used by Reactive Typing effects.\n"
    "This does not stop the current effect; the tray will pick up changes automatically.\n"
    "The slider below controls Reactive Typing brightness (pulse/highlight intensity) and is independent from the manual color override."
)

BindCallback: TypeAlias = Callable[[object | None], None]
AfterCallback: TypeAlias = Callable[[], None]
WindowCloseCallback: TypeAlias = Callable[[], object]
SignalHandler: TypeAlias = Callable[[int | None, object | None], object]
TkExceptionHandler: TypeAlias = Callable[[type[BaseException], BaseException, TracebackType | None], object]


class _ColorCapabilitiesProtocol(Protocol):
    color: object


class _BackendWithCapabilitiesProtocol(Protocol):
    def capabilities(self) -> object | None: ...


class _WrapTargetLabelProtocol(Protocol):
    def pack(self, **kwargs: object) -> object: ...

    def configure(self, **kwargs: object) -> object: ...


class _DescriptionRootProtocol(Protocol):
    def after(self, delay_ms: int, callback: AfterCallback) -> object: ...


class _LifecycleRootProtocol(_DescriptionRootProtocol, Protocol):
    report_callback_exception: TkExceptionHandler

    def protocol(self, name: str, callback: WindowCloseCallback) -> object: ...


class _DescriptionMainProtocol(Protocol):
    def bind(self, sequence: str, callback: BindCallback) -> object: ...

    def winfo_width(self) -> int: ...


class _DescriptionGuiProtocol(Protocol):
    root: _DescriptionRootProtocol
    _wrap_labels: list[object]


class _LifecycleGuiProtocol(Protocol):
    root: _LifecycleRootProtocol

    def _on_close(self) -> object: ...


class _TtkModuleProtocol(Protocol):
    Label: Callable[..., _WrapTargetLabelProtocol]


class _SignalModuleProtocol(Protocol):
    def signal(self, signalnum: int, handler: SignalHandler) -> object: ...


def probe_color_support(
    *,
    select_backend_fn: Callable[[], _BackendWithCapabilitiesProtocol | None],
    logger: logging.Logger,
) -> bool:
    try:
        backend = select_backend_fn()
        caps = backend.capabilities() if backend is not None else None
        if caps is None:
            return True
        if hasattr(caps, "color"):
            return bool(cast(_ColorCapabilitiesProtocol, caps).color)
        return True
    except _BACKEND_CAPABILITY_ERRORS:
        logger.debug(
            "Failed to probe backend capabilities for the reactive color window; assuming RGB support",
            exc_info=True,
        )
        return True


def build_description_section(
    gui: _DescriptionGuiProtocol,
    main: _DescriptionMainProtocol,
    *,
    ttk_module: _TtkModuleProtocol,
    wrap_sync_errors: tuple[type[BaseException], ...],
) -> _WrapTargetLabelProtocol:
    desc = ttk_module.Label(
        main,
        text=_DESCRIPTION_TEXT,
        font=("Sans", 9),
        justify="left",
        wraplength=520,
    )
    desc.pack(pady=(0, 10), fill="x")

    wrap_labels = gui._wrap_labels
    wrap_labels.append(desc)

    def _sync_desc_wrap(_event: object | None = None) -> None:
        try:
            width = int(main.winfo_width())
            if width <= 1:
                return
            wrap = max(220, width - 24)
            for label in wrap_labels:
                cast(_WrapTargetLabelProtocol, label).configure(wraplength=wrap)
        except wrap_sync_errors:
            return

    main.bind("<Configure>", _sync_desc_wrap)
    gui.root.after(0, lambda: _sync_desc_wrap())
    return desc


def install_lifecycle_bindings(
    gui: _LifecycleGuiProtocol,
    *,
    signal_module: _SignalModuleProtocol,
    sigint: int,
) -> None:
    gui.root.protocol("WM_DELETE_WINDOW", gui._on_close)

    original_report_callback_exception = gui.root.report_callback_exception

    def _report_callback_exception(
        exc: type[BaseException],
        val: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if isinstance(val, KeyboardInterrupt):
            gui._on_close()
            return
        original_report_callback_exception(exc, val, tb)

    gui.root.report_callback_exception = _report_callback_exception

    # When launched from a terminal, Ctrl+C sends SIGINT to the whole process group.
    # Use a handler to close cleanly without printing a traceback.
    def _handle_sigint(_signum: int | None = None, _frame: object | None = None) -> object:
        return gui._on_close()

    signal_module.signal(sigint, _handle_sigint)
