from __future__ import annotations

from typing import Callable
from typing import Protocol, TypeAlias

from src.core.secondary_device_routes import SecondaryDeviceRoute

Color: TypeAlias = tuple[int, int, int]


class _UniformConfig(Protocol):
    effect: str
    color: Color | list[int]
    brightness: int


class _UniformTargetState(Protocol):
    config: _UniformConfig
    _target_is_secondary: bool
    _secondary_route: SecondaryDeviceRoute | None


class _UniformTargetRouteState(Protocol):
    target_context: str
    requested_backend: str | None
    _secondary_route: SecondaryDeviceRoute | None
    _target_is_secondary: bool
    _target_label: str


class _UniformDragState(Protocol):
    _pending_color: Color | None
    _last_drag_commit_ts: float
    _last_drag_committed_color: Color | None
    _drag_commit_interval: float


class _UniformStatusLabel(Protocol):
    def config(self, **kwargs: object) -> None: ...


class _UniformRoot(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], None]) -> object: ...


class _UniformStatusGui(Protocol):
    root: _UniformRoot
    status_label: _UniformStatusLabel


def initialize_target_route_state(
    gui: _UniformTargetRouteState,
    *,
    target_context: str | None,
    requested_backend: str | None,
    resolve_secondary_route_fn: Callable[[], SecondaryDeviceRoute | None],
) -> None:
    gui.target_context = str(target_context or "keyboard").strip().lower() or "keyboard"
    gui.requested_backend = str(requested_backend or "").strip().lower() or None
    gui._secondary_route = resolve_secondary_route_fn()
    gui._target_is_secondary = gui._secondary_route is not None
    gui._target_label = str(gui._secondary_route.display_name) if gui._secondary_route is not None else "Keyboard"


def initialize_drag_state(gui: _UniformDragState, *, drag_commit_interval: float = 0.06) -> None:
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = float(drag_commit_interval)


def log_color_apply_failure(exc: Exception, *, debug_enabled: bool, logger: object) -> None:
    if debug_enabled:
        getattr(logger, "exception")("Error setting color")
        return
    getattr(logger, "error")("Error setting color: %s", exc)


def set_status(gui: _UniformStatusGui, msg: str, *, ok: bool, clear_delay_ms: int = 2000) -> None:
    color = "#00ff00" if ok else "#ff0000"
    gui.status_label.config(text=msg, foreground=color)
    gui.root.after(int(clear_delay_ms), lambda: gui.status_label.config(text=""))


def ensure_brightness_nonzero(gui: _UniformTargetState) -> int:
    brightness = int(current_brightness(gui))
    if brightness == 0:
        brightness = 25
        store_brightness(gui, brightness)
    return brightness


def commit_color_to_config(gui: _UniformTargetState, r: int, g: int, b: int) -> None:
    if gui._target_is_secondary:
        store_secondary_color(gui, (r, g, b))
        return

    gui.config.effect = "none"
    gui.config.color = (r, g, b)


def initial_color(gui: _UniformTargetState) -> Color:
    if gui._target_is_secondary:
        return current_secondary_color(gui)
    return tuple(gui.config.color) if isinstance(gui.config.color, list) else gui.config.color


def current_brightness(gui: _UniformTargetState) -> int:
    if not gui._target_is_secondary:
        return int(gui.config.brightness)

    getter = getattr(gui.config, "get_secondary_device_brightness", None)
    if callable(getter) and gui._secondary_route is not None:
        return int(
            getter(
                str(gui._secondary_route.state_key),
                fallback_keys=tuple(filter(None, (gui._secondary_route.config_brightness_attr,))),
                default=25,
            )
        )

    if gui._secondary_route is not None and gui._secondary_route.config_brightness_attr:
        return int(getattr(gui.config, gui._secondary_route.config_brightness_attr, 25) or 25)
    return 25


def store_brightness(gui: _UniformTargetState, brightness: int) -> None:
    if not gui._target_is_secondary:
        gui.config.brightness = brightness
        return

    if gui._secondary_route is None:
        return

    setter = getattr(gui.config, "set_secondary_device_brightness", None)
    if callable(setter):
        setter(
            str(gui._secondary_route.state_key),
            int(brightness),
            compatibility_key=gui._secondary_route.config_brightness_attr,
        )
        return

    if gui._secondary_route.config_brightness_attr:
        setattr(gui.config, gui._secondary_route.config_brightness_attr, int(brightness))


def current_secondary_color(gui: _UniformTargetState) -> Color:
    if gui._secondary_route is None:
        return (255, 0, 0)

    getter = getattr(gui.config, "get_secondary_device_color", None)
    if callable(getter):
        return tuple(
            getter(
                str(gui._secondary_route.state_key),
                fallback_keys=tuple(filter(None, (gui._secondary_route.config_color_attr,))),
                default=(255, 0, 0),
            )
        )

    if gui._secondary_route.config_color_attr:
        return tuple(getattr(gui.config, gui._secondary_route.config_color_attr, (255, 0, 0)))
    return (255, 0, 0)


def store_secondary_color(gui: _UniformTargetState, color: Color) -> None:
    if gui._secondary_route is None:
        return

    setter = getattr(gui.config, "set_secondary_device_color", None)
    if callable(setter):
        setter(
            str(gui._secondary_route.state_key),
            color,
            compatibility_key=gui._secondary_route.config_color_attr,
            default=(255, 0, 0),
        )
        return

    if gui._secondary_route.config_color_attr:
        setattr(gui.config, gui._secondary_route.config_color_attr, color)