"""Compatibility adapters for the tray runtime transition owner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, cast

from .runtime_coordinator import ConditionalTransitionResult, TrayRuntimeCoordinator, UiRefreshRequest

_T = TypeVar("_T")


class _DeferredUiTray(Protocol):
    def _refresh_ui(self, *, animate_icon: bool = True) -> None: ...

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _update_menu(self) -> None: ...


def _coordinator_or_none(tray: object) -> TrayRuntimeCoordinator | None:
    coordinator = getattr(tray, "runtime_coordinator", None)
    return coordinator if isinstance(coordinator, TrayRuntimeCoordinator) else None


def _flush_ui_request(tray: object, request: UiRefreshRequest) -> None:
    ui_tray = cast(_DeferredUiTray, tray)
    if request.icon and request.menu:
        ui_tray._refresh_ui(animate_icon=request.animate_icon)
        return
    if request.icon:
        ui_tray._update_icon(animate=request.animate_icon)
    if request.menu:
        ui_tray._update_menu()


def run_tray_transition(tray: object, action: Callable[[], _T]) -> _T:
    """Run through the production owner, retaining direct fake compatibility."""

    coordinator = _coordinator_or_none(tray)
    if coordinator is None:
        return action()
    return coordinator.run(
        action,
        after=lambda request: _flush_ui_request(tray, request),
    )


def capture_transition_revision(tray: object) -> int | None:
    """Capture the production transition revision before an external probe."""

    coordinator = _coordinator_or_none(tray)
    return coordinator.capture_revision() if coordinator is not None else None


def active_transition_revision(tray: object) -> int | None:
    """Return the production command revision from its owner thread."""

    coordinator = _coordinator_or_none(tray)
    return coordinator.active_revision() if coordinator is not None else None


def run_tray_observation_if_current(
    tray: object,
    revision: int | None,
    action: Callable[[], _T],
) -> ConditionalTransitionResult[_T]:
    """Apply a sensor observation unless a newer transition superseded it."""

    coordinator = _coordinator_or_none(tray)
    if coordinator is None or revision is None:
        return ConditionalTransitionResult(accepted=True, value=action())
    return coordinator.run_if_current(
        revision,
        action,
        after=lambda request: _flush_ui_request(tray, request),
    )


def defer_ui_refresh(
    tray: object,
    *,
    icon: bool = False,
    menu: bool = False,
    animate_icon: bool = True,
) -> bool:
    """Record presentation work when called inside an owned transition."""

    coordinator = _coordinator_or_none(tray)
    return bool(
        coordinator is not None
        and coordinator.request_ui(
            icon=icon,
            menu=menu,
            animate_icon=animate_icon,
        )
    )
