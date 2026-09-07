from __future__ import annotations

from pathlib import Path

import pytest

from keyrgb.core.backends.base import BackendStability, ExperimentalEvidence
from keyrgb.core.backends.exceptions import BackendIOError
from keyrgb.core.backends.ite8258_perkey_chassis import protocol
from keyrgb.core.backends.ite8258_perkey_chassis.backend import (
    Ite8258ChassisBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from keyrgb.core.backends.ite8258_perkey_chassis.device import Ite8258ChassisKeyboardDevice


def test_backend_reports_research_backed_experimental_metadata() -> None:
    backend = Ite8258ChassisBackend()

    assert backend.name == "ite8258_perkey_chassis"
    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED
    caps = backend.capabilities()
    assert caps.per_key is True
    assert caps.hardware_effects is True
    assert backend.dimensions() == (protocol.KEYBOARD_NUM_ROWS, protocol.KEYBOARD_NUM_COLS)
    assert backend.diagnostics()["keyboard_matrix"] == {
        "rows": 7,
        "cols": 20,
        "matrix_cells": 140,
        "mapped_leds": 101,
        "keyboard_led_ids": 101,
        "sparse": True,
        "sparse_holes": 39,
        "row_mapped_counts": [20, 18, 17, 17, 15, 11, 3],
    }
    assert set(backend.effects()) == {
        "rainbow",
        "rainbow_wave",
        "color_change",
        "color_pulse",
        "color_wave",
        "smooth",
        "rain",
        "ripple",
        "audio_bounce",
        "audio_ripple",
        "type",
    }
    assert backend.colors() == {}


def test_find_matching_supported_hidraw_device_uses_forced_existing_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forced = tmp_path / "hidraw11"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv(protocol.HIDRAW_PATH_ENV, str(forced))

    info = _find_matching_supported_hidraw_device()

    assert info is not None
    assert info.devnode == forced
    assert info.vendor_id == protocol.VENDOR_ID
    assert info.product_id == protocol.SUPPORTED_PRODUCT_IDS[0]


def test_backend_probe_reports_unavailable_when_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert "disabled" in result.reason.lower()


def test_backend_probe_reports_unavailable_when_no_matching_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._find_matching_supported_hidraw_device",
        lambda: None,
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert result.reason == "no matching hidraw device"


def test_backend_probe_reports_detected_but_disabled_until_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC197
        devnode = Path("/dev/hidraw11")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is False
    assert "experimental backend disabled" in result.reason.lower()
    assert result.identifiers["usb_pid"] == "0xc197"
    assert result.identifiers["hidraw"] == "/dev/hidraw11"


def test_backend_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0xC197
        devnode = Path("/dev/hidraw11")
        hid_name = "ITE Device(8258)"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8258ChassisBackend().probe()

    assert result.available is True
    assert result.confidence == 83
    assert result.identifiers["hidraw"] == "/dev/hidraw11"


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._find_matching_supported_hidraw_device",
        lambda: None,
    )

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_backend_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_reraises_non_permission_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    err = OSError("transport failed")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8258ChassisBackend().get_device()


def test_backend_get_device_returns_keyboard_device_when_transport_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    sent: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            sent.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = Path("/dev/hidraw11")

    monkeypatch.setattr(
        "keyrgb.core.backends.ite8258_perkey_chassis.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8258ChassisBackend().get_device()

    assert isinstance(device, Ite8258ChassisKeyboardDevice)
    device.set_effect({"name": "color_wave", "color": (0x12, 0x34, 0x56), "direction": "left", "brightness": 50})
    assert sent[0][:5].hex() == "07c8c00301"
    assert sent[1][:6].hex() == "07d0c0030201"
    assert sent[2][1] == protocol.SAVE_PROFILE
    assert sent[3][:5].hex() == "07cec00309"


def test_backend_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8258ChassisBackend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8258ChassisBackend().is_available() is True
