from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from src.core.backends.shared_hidraw_transport import (
    HidrawTransportProxy,
    SharedHidrawTransportManager,
)


class _MockTransport:
    def __init__(self, *, fail_send: OSError | None = None, fail_write: OSError | None = None) -> None:
        self.closed = False
        self.send_log: list[bytes] = []
        self.write_log: list[bytes] = []
        self._fd: int | None = 1
        self._fail_send = fail_send
        self._fail_write = fail_write

    def send_feature_report(self, report: bytes) -> int:
        if self._fail_send is not None:
            raise self._fail_send
        self.send_log.append(bytes(report))
        return len(report)

    def write_output_report(self, report: bytes) -> int:
        if self._fail_write is not None:
            raise self._fail_write
        self.write_log.append(bytes(report))
        return len(report)

    def close(self) -> None:
        self.closed = True
        self._fd = None


def _make_manager_with_mock(
    opener_result: _MockTransport | None = None,
) -> tuple[SharedHidrawTransportManager, _MockTransport, list[int], Callable[[], _MockTransport]]:
    manager = SharedHidrawTransportManager()
    mock = opener_result if opener_result is not None else _MockTransport()
    call_log: list[int] = []

    def _opener() -> _MockTransport:
        call_log.append(len(call_log) + 1)
        return mock

    return manager, mock, call_log, _opener


def test_acquire_opens_transport_and_release_closes_it() -> None:
    manager, mock, calls, opener = _make_manager_with_mock()

    proxy = manager.acquire("ite8258_perkey_chassis", opener)
    assert proxy.is_alive is True
    assert mock.closed is False
    assert len(calls) == 1

    proxy.close()
    assert mock.closed is True
    assert proxy.is_alive is False


def test_multiple_acquires_share_transport_and_close_after_last_release() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxy_a = manager.acquire("ite8258_perkey_chassis", opener)
    proxy_b = manager.acquire("ite8258_perkey_chassis", opener)
    proxy_c = manager.acquire("ite8258_perkey_chassis", opener)

    assert mock.closed is False

    proxy_a.close()
    assert mock.closed is False

    proxy_b.close()
    assert mock.closed is False

    proxy_c.close()
    assert mock.closed is True


def test_release_order_does_not_matter() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxies: list[HidrawTransportProxy] = [manager.acquire("ite8258_perkey_chassis", opener) for _ in range(5)]

    for proxy in reversed(proxies):
        proxy.close()

    assert mock.closed is True


def test_double_release_is_idempotent() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxy = manager.acquire("ite8258_perkey_chassis", opener)
    proxy.close()
    proxy.close()  # should not raise or double-close

    assert mock.closed is True


def test_invalidation_closes_transport_and_marks_proxies_dead() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxy_a = manager.acquire("ite8258_perkey_chassis", opener)
    proxy_b = manager.acquire("ite8258_perkey_chassis", opener)

    manager.invalidate("ite8258_perkey_chassis")

    assert mock.closed is True
    assert proxy_a.is_alive is False
    assert proxy_b.is_alive is False

    with pytest.raises(RuntimeError, match="no longer valid"):
        proxy_a.send_feature_report(b"x")


def test_operations_after_release_raise() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxy = manager.acquire("ite8258_perkey_chassis", opener)
    proxy.close()

    with pytest.raises(RuntimeError, match="no longer valid"):
        proxy.send_feature_report(b"x")


def test_acquire_after_invalidation_opens_fresh_transport() -> None:
    manager = SharedHidrawTransportManager()
    mocks: list[_MockTransport] = []

    def _opener() -> _MockTransport:
        mock = _MockTransport()
        mocks.append(mock)
        return mock

    proxy1 = manager.acquire("ite8258_perkey_chassis", _opener)
    proxy1.send_feature_report(b"hello")
    manager.invalidate("ite8258_perkey_chassis")

    proxy2 = manager.acquire("ite8258_perkey_chassis", _opener)
    proxy2.send_feature_report(b"world")

    assert len(mocks) == 2
    assert mocks[0].closed is True
    assert mocks[0].send_log == [b"hello"]
    assert mocks[1].send_log == [b"world"]


def test_send_and_write_are_routed_through_underlying_transport() -> None:
    manager, mock, _calls, opener = _make_manager_with_mock()

    proxy = manager.acquire("ite8258_perkey_chassis", opener)
    proxy.send_feature_report(b"feature")
    proxy.write_output_report(b"output")

    assert mock.send_log == [b"feature"]
    assert mock.write_log == [b"output"]


def test_shared_proxy_uses_transport_level_pacing_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.backends.ite8291_perkey.hidraw import HidrawFeatureOutputTransport

    sleeps: list[float] = []
    ioctl_payloads: list[bytes] = []
    monkeypatch.setenv("KEYRGB_ITE8258_PERKEY_CHASSIS_REPORT_DELAY_MS", "2")
    monkeypatch.setattr("src.core.backends._report_pacing.time.sleep", sleeps.append)

    def fake_ioctl(fd: int, request: int, payload: bytearray, mutate_flag: bool) -> None:
        _ = fd, request, mutate_flag
        ioctl_payloads.append(bytes(payload))

    monkeypatch.setattr("src.core.backends.ite8291_perkey.hidraw.fcntl.ioctl", fake_ioctl)

    transport = HidrawFeatureOutputTransport.__new__(HidrawFeatureOutputTransport)
    transport.devnode = Path("/dev/hidraw-test")
    transport._backend_name = "ite8258_perkey_chassis"
    transport._fd = -1

    manager = SharedHidrawTransportManager()
    proxy = manager.acquire("ite8258_perkey_chassis", lambda: transport)

    assert proxy.send_feature_report(b"\x08\x02") == 2
    assert ioctl_payloads == [b"\x08\x02"]
    assert sleeps == [0.002]


def test_write_output_report_returns_none_when_transport_lacks_method() -> None:
    class _NoWriteTransport:
        _fd = 1

        def send_feature_report(self, report: bytes) -> int:
            return len(report)

        def close(self) -> None:
            self._fd = None

    manager = SharedHidrawTransportManager()
    mock = _NoWriteTransport()

    proxy = manager.acquire("ite8258_perkey_chassis", lambda: mock)
    assert proxy.write_output_report(b"output") is None


def test_manager_is_alive_false_for_unknown_backend() -> None:
    manager = SharedHidrawTransportManager()
    assert manager.is_alive("unknown") is False


def test_different_backends_have_independent_transports() -> None:
    manager = SharedHidrawTransportManager()
    mocks: dict[str, _MockTransport] = {}

    def _opener(name: str) -> _MockTransport:
        mock = _MockTransport()
        mocks[name] = mock
        return mock

    proxy_a = manager.acquire("backend-a", lambda: _opener("a"))
    proxy_b = manager.acquire("backend-b", lambda: _opener("b"))

    proxy_a.send_feature_report(b"to-a")
    proxy_b.send_feature_report(b"to-b")

    assert mocks["a"].send_log == [b"to-a"]
    assert mocks["b"].send_log == [b"to-b"]

    proxy_a.close()
    assert mocks["a"].closed is True
    assert mocks["b"].closed is False

    proxy_b.close()
    assert mocks["b"].closed is True


def test_send_failure_invalidates_transport_and_re_raises() -> None:
    manager = SharedHidrawTransportManager()
    err = OSError(19, "No such device")
    mock = _MockTransport(fail_send=err)

    proxy = manager.acquire("ite8258_perkey_chassis", lambda: mock)

    with pytest.raises(OSError, match="No such device"):
        proxy.send_feature_report(b"x")

    assert mock.closed is True
    assert proxy.is_alive is False


def test_write_failure_invalidates_transport_and_re_raises() -> None:
    manager = SharedHidrawTransportManager()
    err = OSError(5, "Input/output error")
    mock = _MockTransport(fail_write=err)

    proxy = manager.acquire("ite8258_perkey_chassis", lambda: mock)

    with pytest.raises(OSError, match="Input/output error"):
        proxy.write_output_report(b"x")

    assert mock.closed is True
    assert proxy.is_alive is False


def test_concurrent_writes_are_serialized() -> None:
    """The manager serializes HID writes per backend to avoid packet interleaving."""
    manager = SharedHidrawTransportManager()

    class _SlowTransport:
        _fd = 1

        def __init__(self) -> None:
            self.send_log: list[tuple[float, bytes]] = []
            self._lock = threading.Lock()

        def send_feature_report(self, report: bytes) -> int:
            start = time.monotonic()
            time.sleep(0.02)
            with self._lock:
                self.send_log.append((start, bytes(report)))
            return len(report)

        def close(self) -> None:
            self._fd = None

    mock = _SlowTransport()
    proxies = [manager.acquire("ite8258_perkey_chassis", lambda: mock) for _ in range(4)]

    threads: list[threading.Thread] = []
    for i, proxy in enumerate(proxies):
        t = threading.Thread(target=proxy.send_feature_report, args=(bytes([i]),))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    for proxy in proxies:
        proxy.close()

    # Each send should be non-overlapping; with 20ms sleeps, interleaving would
    # show starts within a few milliseconds. Assert gaps are meaningful.
    starts: Sequence[float] = [entry[0] for entry in mock.send_log]
    assert len(starts) == 4
    # Sort by start time and ensure each started at least 10ms after the previous.
    sorted_starts = sorted(starts)
    for i in range(1, len(sorted_starts)):
        assert sorted_starts[i] - sorted_starts[i - 1] >= 0.01


def test_proxy_close_after_manager_destroyed_does_not_raise() -> None:
    manager = SharedHidrawTransportManager()
    mock = _MockTransport()
    proxy = manager.acquire("ite8258_perkey_chassis", lambda: mock)

    del manager

    # Force collection so the manager's __del__ may run. Even if it doesn't,
    # close() should tolerate a dead weakref gracefully.
    proxy.close()
