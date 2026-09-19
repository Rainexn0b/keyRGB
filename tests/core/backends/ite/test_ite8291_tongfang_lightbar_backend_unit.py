from __future__ import annotations

import os

import pytest

from keyrgb.core.backends.base import BackendRole, BackendStability, ExperimentalEvidence
from keyrgb.core.backends.exceptions import BackendIOError
from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang import (
    BACKEND_REGISTRATION,
    backend as tongfang_backend_module,
    protocol as tongfang_protocol,
)
from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend import (
    BACKEND_NAME,
    Ite8291TongfangLightbarBackend,
    _find_matching_supported_hidraw_device,
    _open_matching_transport,
)
from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.device import (
    Ite8291TongfangLightbarDevice,
)


def test_tongfang_lightbar_registration_is_auxiliary_experimental() -> None:
    assert BACKEND_REGISTRATION.metadata.name == "ite8291_none_chassis_lightbar_tongfang"
    assert BACKEND_REGISTRATION.metadata.role is BackendRole.AUXILIARY
    assert BACKEND_REGISTRATION.metadata.provider == "usb-userspace"
    assert BACKEND_REGISTRATION.metadata.stability is BackendStability.EXPERIMENTAL
    assert BACKEND_REGISTRATION.metadata.experimental_evidence is ExperimentalEvidence.REVERSE_ENGINEERED
    assert BACKEND_REGISTRATION.metadata.priority == 96


def test_tongfang_lightbar_backend_metadata_matches_registration() -> None:
    backend = Ite8291TongfangLightbarBackend()

    assert backend.name == BACKEND_NAME == "ite8291_none_chassis_lightbar_tongfang"
    assert backend.priority == 96
    assert backend.stability == BackendStability.EXPERIMENTAL
    assert backend.experimental_evidence == ExperimentalEvidence.REVERSE_ENGINEERED


def test_tongfang_lightbar_capabilities_dimensions_effects_colors() -> None:
    backend = Ite8291TongfangLightbarBackend()
    capabilities = backend.capabilities()

    assert capabilities.brightness is True
    assert capabilities.color is True
    assert capabilities.per_key is False
    # Conservatively unadvertised: secondary UI does not expose/validate effects yet.
    assert capabilities.hardware_effects is False
    assert backend.dimensions() == (1, 22)
    assert backend.effects() == {}
    assert backend.colors() == {}


def test_tongfang_lightbar_probe_reports_detected_device_but_requires_opt_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    hidraw_path = tmp_path / "hidraw-test"
    hidraw_path.write_bytes(b"")

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)
    monkeypatch.setenv(tongfang_protocol.HIDRAW_PATH_ENV, os.fspath(hidraw_path))

    probe = Ite8291TongfangLightbarBackend().probe()

    assert probe.available is False
    assert "experimental backend disabled" in probe.reason.lower()
    assert probe.identifiers["usb_vid"] == "0x048d"
    assert probe.identifiers["usb_pid"] == "0x6005"
    assert probe.identifiers["hidraw"] == os.fspath(hidraw_path)
    assert probe.identifiers["usage_page"] == "0xff03"
    assert probe.identifiers["usage"] == "0x01"


def test_tongfang_lightbar_probe_reports_missing_device_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.delenv(tongfang_protocol.HIDRAW_PATH_ENV, raising=False)
    monkeypatch.setattr(
        tongfang_backend_module,
        "_find_matching_supported_hidraw_device",
        lambda: None,
    )

    probe = Ite8291TongfangLightbarBackend().probe()

    assert probe.available is False
    assert "no matching hidraw device" in probe.reason
    assert probe.identifiers["usb_vid"] == "0x048d"
    assert probe.identifiers["usb_pid"] == "0x6005"
    assert probe.identifiers["usage_page"] == "0xff03"
    assert probe.identifiers["usage"] == "0x01"


def test_tongfang_lightbar_probe_reports_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")

    probe = Ite8291TongfangLightbarBackend().probe()

    assert probe.available is False
    assert "KEYRGB_DISABLE_USB_SCAN" in probe.reason
    assert probe.confidence == 0


def test_find_matching_supported_hidraw_device_uses_forced_existing_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    forced = tmp_path / "hidraw9"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv(tongfang_protocol.HIDRAW_PATH_ENV, str(forced))

    info = _find_matching_supported_hidraw_device()

    assert info is not None
    assert info.devnode == forced
    assert info.vendor_id == tongfang_protocol.VENDOR_ID
    assert info.product_id == tongfang_protocol.DEFAULT_PRODUCT_ID == 0x6005
    assert info.hid_id == f"forced:{tongfang_protocol.VENDOR_ID:04x}:{tongfang_protocol.DEFAULT_PRODUCT_ID:04x}"


def test_tongfang_lightbar_probe_reports_available_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyMatch:
        vendor_id = 0x048D
        product_id = 0x6005
        devnode = "/dev/hidraw7"
        hid_name = "ITE Device(8291)"
        hid_id = "0003:048D:6005"

    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._find_matching_supported_hidraw_device",
        lambda: DummyMatch(),
    )

    result = Ite8291TongfangLightbarBackend().probe()

    assert result.available is True
    assert result.confidence <= 83
    assert result.identifiers["usb_pid"] == "0x6005"
    assert result.identifiers["hidraw"] == "/dev/hidraw7"
    assert result.identifiers["usage_page"] == "0xff03"
    assert result.identifiers["usage"] == "0x01"


def test_tongfang_lightbar_get_device_requires_experimental_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    with pytest.raises(RuntimeError, match="experimental"):
        Ite8291TongfangLightbarBackend().get_device()


def test_open_matching_transport_raises_when_no_supported_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._find_matching_supported_hidraw_device",
        lambda: None,
    )

    with pytest.raises(FileNotFoundError, match="No hidraw device found"):
        _open_matching_transport()


def test_tongfang_lightbar_get_device_wraps_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = PermissionError("permission denied")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(PermissionError, match="udev rules"):
        Ite8291TongfangLightbarBackend().get_device()


def test_tongfang_lightbar_get_device_reraises_transport_failure_as_io_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = RuntimeError("transport failed")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(BackendIOError, match="transport failed"):
        Ite8291TongfangLightbarBackend().get_device()


def test_tongfang_lightbar_get_device_propagates_unexpected_open_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    err = AssertionError("unexpected transport bug")
    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._open_matching_transport",
        lambda: (_ for _ in ()).throw(err),
    )

    with pytest.raises(AssertionError, match="unexpected transport bug"):
        Ite8291TongfangLightbarBackend().get_device()


def test_tongfang_lightbar_get_device_returns_device_when_transport_opens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    seen_features: list[bytes] = []
    seen_outputs: list[bytes] = []

    class DummyTransport:
        def send_feature_report(self, report: bytes) -> int:
            seen_features.append(bytes(report))
            return len(report)

        def write_output_report(self, report: bytes) -> int:
            seen_outputs.append(bytes(report))
            return len(report)

    class DummyInfo:
        devnode = "/dev/hidraw7"
        product_id = 0x6005

    monkeypatch.setattr(
        "keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend._open_matching_transport",
        lambda: (DummyTransport(), DummyInfo()),
    )

    device = Ite8291TongfangLightbarBackend().get_device()

    assert isinstance(device, Ite8291TongfangLightbarDevice)
    device.set_color((0x12, 0x34, 0x56), brightness=50)
    assert seen_features[0] == bytes((0x00, 0x08, 0x02, 0x33, 0x00, 0x19, 0x08, 0x00, 0x00))
    assert len(seen_outputs[0]) == 65


def test_tongfang_lightbar_is_available_reflects_probe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Ite8291TongfangLightbarBackend, "probe", lambda self: type("Probe", (), {"available": True})())

    assert Ite8291TongfangLightbarBackend().is_available() is True
