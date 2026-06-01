from __future__ import annotations

import logging

import pytest

from src.core.backends.ite8291r3.usb import PyUsbTransport
from src.core.backends.ite8291r3 import usb as usb_module


class _FakeUsbUtil:
    CTRL_OUT = 0x21
    CTRL_TYPE_CLASS = 0x01
    CTRL_RECIPIENT_INTERFACE = 0x01
    CTRL_IN = 0xA1

    def build_request_type(self, direction: int, request_type: int, recipient: int) -> int:
        return int(direction) | int(request_type) | int(recipient)

    def dispose_devices(self, device: object) -> None:
        return None


class _FakeDevice:
    def __init__(self) -> None:
        self.ctrl_result: bytes | int = 0
        self.write_result: int = 0

    def ctrl_transfer(self, _bm_request_type: int, _b_request: int, _w_value: int, _w_index: int, data_or_w_length: bytes | int) -> object:
        if isinstance(data_or_w_length, int):
            return self.ctrl_result
        return self.write_result

    def write(self, _endpoint: int, _data: bytes) -> int:
        return int(self.write_result)

    def attach_kernel_driver(self, _interface_number: int) -> object:
        return None


def _build_transport(device: _FakeDevice) -> PyUsbTransport:
    return PyUsbTransport(
        device=device,
        usb_util=_FakeUsbUtil(),
        out_endpoint_address=0x01,
        interface_number=1,
    )


def test_send_control_report_logs_slow_transfer_when_debug_enabled(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    times = iter((100.0, 100.05))
    monkeypatch.setattr(usb_module.time, "monotonic", lambda: next(times))

    device = _FakeDevice()
    device.write_result = 4
    transport = _build_transport(device)

    with caplog.at_level(logging.INFO):
        assert transport.send_control_report(b"\x01\x02\x03\x04") == 4

    assert any("EVENT ite8291r3:usb_transfer_slow direction=out kind=control_write" in record.message for record in caplog.records)


def test_read_control_report_logs_length_mismatch_when_debug_enabled(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    times = iter((200.0, 200.001))
    monkeypatch.setattr(usb_module.time, "monotonic", lambda: next(times))

    device = _FakeDevice()
    device.ctrl_result = b"\x10\x20\x30"
    transport = _build_transport(device)

    with caplog.at_level(logging.INFO):
        assert transport.read_control_report(8) == b"\x10\x20\x30"

    assert any("EVENT ite8291r3:usb_transfer_length_mismatch direction=in kind=control_read expected=8 actual=3" in record.message for record in caplog.records)


def test_write_data_logs_length_mismatch_when_debug_enabled(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    times = iter((300.0, 300.001))
    monkeypatch.setattr(usb_module.time, "monotonic", lambda: next(times))

    device = _FakeDevice()
    device.write_result = 2
    transport = _build_transport(device)

    with caplog.at_level(logging.INFO):
        assert transport.write_data(b"\xAA\xBB\xCC") == 2

    assert any("EVENT ite8291r3:usb_transfer_length_mismatch direction=out kind=data_write expected=3 actual=2" in record.message for record in caplog.records)