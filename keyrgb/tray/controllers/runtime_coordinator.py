"""Single-owner execution for low-frequency tray runtime transitions."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar, cast

_T = TypeVar("_T")


class CoordinatorStoppedError(RuntimeError):
    """Raised when a transition is submitted after coordinator shutdown."""


@dataclass(frozen=True)
class UiRefreshRequest:
    """Coalesced presentation work requested by one root transition."""

    icon: bool = False
    menu: bool = False
    animate_icon: bool = True

    @property
    def requested(self) -> bool:
        return self.icon or self.menu

    def merged(self, *, icon: bool, menu: bool, animate_icon: bool) -> UiRefreshRequest:
        return UiRefreshRequest(
            icon=self.icon or icon,
            menu=self.menu or menu,
            animate_icon=self.animate_icon and animate_icon,
        )


@dataclass(frozen=True)
class ConditionalTransitionResult(Generic[_T]):
    """Result of a revision-gated transition submission."""

    accepted: bool
    value: _T | None = None


@dataclass
class _TransitionCommand:
    action: Callable[[], object]
    revision: int
    completed: threading.Event = field(default_factory=threading.Event)
    value: object = None
    error: BaseException | None = None
    ui_request: UiRefreshRequest = field(default_factory=UiRefreshRequest)


_STOP = object()


class TrayRuntimeCoordinator:
    """Execute complete tray transitions on one FIFO owner thread."""

    def __init__(self) -> None:
        self._commands: queue.Queue[_TransitionCommand | object] = queue.Queue()
        self._state_lock = threading.Lock()
        self._accepting = True
        self._revision = 0
        self._owner_ident: int | None = None
        self._active_revision: int | None = None
        self._active_ui_request: UiRefreshRequest | None = None
        self._thread: threading.Thread | None = None

    def capture_revision(self) -> int:
        """Return the latest accepted root-transition revision."""

        with self._state_lock:
            return self._revision

    def start(self) -> None:
        """Start the lazy owner thread before runtime producers are launched."""

        with self._state_lock:
            if not self._accepting:
                raise CoordinatorStoppedError("tray runtime coordinator is stopped")
            self._start_thread_locked()

    def active_revision(self) -> int | None:
        """Return the executing root revision when called by the owner."""

        if threading.get_ident() != self._owner_ident:
            return None
        return self._active_revision

    def run(
        self,
        action: Callable[[], _T],
        *,
        after: Callable[[UiRefreshRequest], None] | None = None,
    ) -> _T:
        """Run one transition synchronously, executing nested calls inline."""

        if threading.get_ident() == self._owner_ident:
            return action()

        command = self._submit(action, expected_revision=None)
        assert command is not None
        return cast(_T, self._wait_for(command, after=after))

    def run_if_current(
        self,
        revision: int,
        action: Callable[[], _T],
        *,
        after: Callable[[UiRefreshRequest], None] | None = None,
    ) -> ConditionalTransitionResult[_T]:
        """Run an observation only if no newer transition was accepted."""

        if threading.get_ident() == self._owner_ident:
            with self._state_lock:
                if int(revision) != self._revision:
                    return ConditionalTransitionResult(accepted=False)
            return ConditionalTransitionResult(accepted=True, value=action())

        command = self._submit(action, expected_revision=int(revision))
        if command is None:
            return ConditionalTransitionResult(accepted=False)
        return ConditionalTransitionResult(
            accepted=True,
            value=cast(_T, self._wait_for(command, after=after)),
        )

    def request_ui(
        self,
        *,
        icon: bool = False,
        menu: bool = False,
        animate_icon: bool = True,
    ) -> bool:
        """Coalesce UI work while the owner executes a root transition."""

        if threading.get_ident() != self._owner_ident or self._active_ui_request is None:
            return False
        self._active_ui_request = self._active_ui_request.merged(
            icon=bool(icon),
            menu=bool(menu),
            animate_icon=bool(animate_icon),
        )
        return True

    def stop_and_drain(self, *, timeout_s: float) -> bool:
        """Stop accepting work, drain accepted commands, and join the owner."""

        with self._state_lock:
            if self._accepting:
                self._accepting = False
                if self._thread is not None:
                    self._commands.put(_STOP)
            thread = self._thread
        if thread is None:
            return True
        if threading.get_ident() == self._owner_ident:
            return False
        thread.join(timeout=max(0.0, float(timeout_s)))
        return not thread.is_alive()

    def _submit(
        self,
        action: Callable[[], _T],
        *,
        expected_revision: int | None,
    ) -> _TransitionCommand | None:
        with self._state_lock:
            if not self._accepting:
                raise CoordinatorStoppedError("tray runtime coordinator is stopped")
            if expected_revision is not None and expected_revision != self._revision:
                return None
            self._start_thread_locked()
            self._revision += 1
            command = _TransitionCommand(
                action=cast(Callable[[], object], action),
                revision=self._revision,
            )
            self._commands.put(command)
            return command

    def _start_thread_locked(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="keyrgb-tray-runtime",
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _wait_for(
        command: _TransitionCommand,
        *,
        after: Callable[[UiRefreshRequest], None] | None,
    ) -> object:
        command.completed.wait()
        if command.error is not None:
            raise command.error
        if after is not None and command.ui_request.requested:
            after(command.ui_request)
        return command.value

    def _run(self) -> None:
        self._owner_ident = threading.get_ident()
        while True:
            command = self._commands.get()
            if command is _STOP:
                return
            typed_command = cast(_TransitionCommand, command)
            self._active_revision = typed_command.revision
            self._active_ui_request = UiRefreshRequest()
            try:
                typed_command.value = typed_command.action()
            except (KeyboardInterrupt, SystemExit) as exc:
                typed_command.error = exc
            except Exception as exc:  # noqa: BLE001  # @quality-exception exception-transparency: owner-thread command boundary captures and re-raises every transition failure on its synchronous caller
                typed_command.error = exc
            finally:
                typed_command.ui_request = self._active_ui_request
                self._active_ui_request = None
                self._active_revision = None
                typed_command.completed.set()
