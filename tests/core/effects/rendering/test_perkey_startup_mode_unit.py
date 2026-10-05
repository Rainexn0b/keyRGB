from __future__ import annotations

import logging
from threading import Event, RLock

import pytest

from keyrgb.core.backends.ite8291r3_perkey import protocol
from keyrgb.core.backends.ite8291r3_perkey.backend import Ite8291r3Backend
from keyrgb.core.backends.ite8291r3_perkey.device import Ite8291r3KeyboardDevice
from keyrgb.core.effects.device import _BrightnessLoggingKeyboardProxy
from keyrgb.core.effects.engine import EffectsEngine
from keyrgb.core.effects.fades import prime_per_key_frame


class _Controller:
    """In-memory ITE transport, including the captured inactive startup state."""

    def __init__(self, status: bytes, *, accept_mode: bool = True) -> None:
        self.status = bytearray(status)
        self.accept_mode = accept_mode
        self.controls: list[bytes] = []
        self.events: list[str] = []
        self.device = Ite8291r3KeyboardDevice(self.send, self.read, self.row, report_delay_s=0.0)

    def send(self, report: bytes) -> int:
        self.controls.append(report)
        if report[0] == protocol.Commands.SET_BRIGHTNESS:
            self.status[4] = report[2]
            self.events.append("brightness")
        elif report[0] == protocol.Commands.SET_EFFECT:
            self.events.append("mode")
            if self.accept_mode:
                self.status[1:] = report[1:]
        return len(report)

    def read(self, length: int) -> bytes:
        assert length == 8
        return bytes(self.status)

    def row(self, payload: bytes) -> int:
        self.events.append("row")
        return len(payload)

    @property
    def mode_reports(self) -> list[bytes]:
        return [report for report in self.controls if report[0] == protocol.Commands.SET_EFFECT]


def _prime(device: object) -> bool:
    return prime_per_key_frame(
        kb=device,  # type: ignore[arg-type]
        kb_lock=RLock(),
        per_key_colors={(0, 0): (255, 0, 0)},
        current_color=(144, 255, 49),
        brightness=40,
    )


@pytest.mark.parametrize("with_logging_proxy", [False, True])
def test_prime_recovers_captured_inactive_user_mode_at_nonzero_brightness(with_logging_proxy: bool) -> None:
    controller = _Controller(bytes.fromhex("880033f028000000"))
    device = controller.device
    assert device.is_off() is False
    assert device.get_brightness() == 40
    keyboard = (
        _BrightnessLoggingKeyboardProxy(device, logger=logging.getLogger(__name__))  # type: ignore[arg-type]
        if with_logging_proxy
        else device
    )

    assert _prime(keyboard) is True

    assert controller.mode_reports == [bytes.fromhex("0802330028000000")]
    assert controller.events == ["row"] * 6 + ["brightness", "mode"]
    assert controller.status.hex() == "8802330028000000"


def test_prime_preserves_active_user_mode_without_reassert_or_save() -> None:
    controller = _Controller(bytes.fromhex("8802330028000000"))

    assert _prime(controller.device) is True

    assert controller.mode_reports == []
    assert controller.events == ["row"] * 6 + ["brightness"]


def test_prime_reclaims_non_user_mode_at_nonzero_brightness() -> None:
    controller = _Controller(bytes.fromhex("8802030028000000"))

    assert _prime(controller.device) is True

    assert controller.mode_reports == [bytes.fromhex("0802330028000000")]


def test_prime_does_not_publish_success_when_mode_reassert_is_ignored(caplog) -> None:
    controller = _Controller(bytes.fromhex("880033f028000000"), accept_mode=False)

    with caplog.at_level(logging.WARNING):
        assert _prime(controller.device) is False

    assert len(controller.mode_reports) == 1
    assert "user mode" in caplog.text.lower()


@pytest.mark.parametrize(
    ("status", "active", "off"),
    [
        ("8802330028000000", True, False),
        ("8802330000000000", True, False),  # Native sleep remains distinct from explicit off.
        ("880033f028000000", False, False),
        ("8801030028000000", False, True),
        ("8802030028000000", False, False),
    ],
)
def test_ite_user_mode_probe_preserves_off_and_sleep_semantics(status: str, active: bool, off: bool) -> None:
    controller = _Controller(bytes.fromhex(status))

    assert controller.device.is_user_mode() is active
    assert controller.device.is_off() is off
    assert controller.mode_reports == []


@pytest.mark.parametrize("response", [b"", bytes(7), bytes.fromhex("8002330028000000")])
def test_user_mode_probe_rejects_incomplete_or_wrong_status_response(response: bytes) -> None:
    controller = _Controller(response)

    with pytest.raises(OSError, match="status response"):
        controller.device.is_user_mode()


def test_prime_contains_recoverable_mode_probe_failure(caplog, monkeypatch) -> None:
    controller = _Controller(bytes.fromhex("8802330028000000"))

    def failed_probe() -> bool:
        raise OSError("status read failed")

    monkeypatch.setattr(controller.device, "is_user_mode", failed_probe, raising=False)
    with caplog.at_level(logging.DEBUG):
        assert _prime(controller.device) is False

    assert controller.mode_reports == []
    assert "status read failed" in caplog.text


def test_prime_propagates_unexpected_mode_probe_defect(monkeypatch) -> None:
    controller = _Controller(bytes.fromhex("8802330028000000"))

    def broken_probe() -> bool:
        raise LookupError("unexpected mode probe defect")

    monkeypatch.setattr(controller.device, "is_user_mode", broken_probe, raising=False)
    with pytest.raises(LookupError, match="unexpected mode probe defect"):
        _prime(controller.device)


def test_engine_start_verifies_mode_before_publishing_render_baseline(monkeypatch) -> None:
    controller = _Controller(bytes.fromhex("880033f028000000"))
    engine = EffectsEngine(backend=Ite8291r3Backend())
    # Pytest acquisition deliberately returns NullKeyboard. Inject only the
    # in-memory device; never opt the test into real hardware access.
    engine.kb = controller.device  # type: ignore[assignment]
    engine.device_available = True
    monkeypatch.setattr(engine, "_ensure_device_available", lambda: True)
    engine.per_key_colors = {(0, 0): (255, 0, 0)}
    engine.brightness = 40
    ready = Event()
    worker_status: list[str] = []

    def worker() -> None:
        worker_status.append(controller.status.hex())
        ready.set()
        engine.stop_event.wait(1.0)

    try:
        engine._start_sw_effect(target=worker, prev_color=(0, 0, 0), fade_to_color=(255, 0, 0))
        assert ready.wait(1.0)
        assert worker_status == ["8802330028000000"]
        assert engine._last_hw_mode_brightness == 40
        assert engine._last_rendered_brightness == 40
        assert controller.mode_reports == [bytes.fromhex("0802330028000000")]
    finally:
        engine.close()
