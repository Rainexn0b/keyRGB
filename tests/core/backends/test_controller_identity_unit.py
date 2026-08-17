from __future__ import annotations

from src.core.backends.controller_identity import controller_identity
from src.core.backends.ite8258_perkey_chassis import backend as chassis_backend
from src.core.backends.ite8258_perkey_chassis.profile_coordinator import Ite8258ChassisProfileCoordinator
from src.core.backends.shared_hidraw_transport import SharedHidrawTransportManager


class _MockTransport:
    def __init__(self) -> None:
        self.closed = False
        self.send_log: list[bytes] = []
        self._fd: int | None = 1

    def send_feature_report(self, report: bytes) -> int:
        self.send_log.append(bytes(report))
        return len(report)

    def close(self) -> None:
        self.closed = True
        self._fd = None


def test_controller_identity_includes_hidraw_when_present() -> None:
    assert controller_identity(backend_name="ite8258_perkey_chassis") == "ite8258_perkey_chassis"
    assert (
        controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw3")
        == "ite8258_perkey_chassis:/dev/hidraw3"
    )
    assert controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw3") != controller_identity(
        backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw4"
    )


def test_shared_hidraw_manager_does_not_share_across_controller_identities() -> None:
    manager = SharedHidrawTransportManager()
    transports: dict[str, _MockTransport] = {}

    def _opener(name: str) -> _MockTransport:
        transport = _MockTransport()
        transports[name] = transport
        return transport

    first = controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw3")
    second = controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw4")
    proxy_a = manager.acquire(first, lambda: _opener("a"))
    proxy_b = manager.acquire(second, lambda: _opener("b"))

    proxy_a.send_feature_report(b"left")
    proxy_b.send_feature_report(b"right")

    assert transports["a"].send_log == [b"left"]
    assert transports["b"].send_log == [b"right"]

    proxy_a.close()
    assert transports["a"].closed is True
    assert transports["b"].closed is False


def test_chassis_profile_coordinators_are_isolated_per_controller_identity() -> None:
    chassis_backend._profile_coordinators = {}
    first = controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw3")
    second = controller_identity(backend_name="ite8258_perkey_chassis", hidraw="/dev/hidraw4")

    left = chassis_backend._get_profile_coordinator(first)
    right = chassis_backend._get_profile_coordinator(second)

    assert isinstance(left, Ite8258ChassisProfileCoordinator)
    assert isinstance(right, Ite8258ChassisProfileCoordinator)
    assert left is not right
    assert chassis_backend._get_profile_coordinator(first) is left
