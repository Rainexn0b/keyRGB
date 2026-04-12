from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.core.backends.exceptions import (
    BACKEND_OPEN_RUNTIME_ERRORS,
    BackendBusyError,
    BackendDisconnectedError,
    BackendIOError,
    BackendPermissionError,
)
from src.core.utils.exceptions import is_device_busy, is_device_disconnected, is_permission_denied

from ..base import (
    BackendCapabilities,
    BackendStability,
    ExperimentalEvidence,
    KeyboardBackend,
    KeyboardDevice,
    ProbeResult,
)
from ..policy import experimental_backends_enabled
from . import protocol
from .device import Ite8291KeyboardDevice
from .hidraw import (
    HidrawDeviceInfo,
    HidrawFeatureOutputTransport,
    find_matching_hidraw_device,
    open_matching_hidraw_transport,
)


def _find_matching_supported_hidraw_device() -> HidrawDeviceInfo | None:
    return find_matching_hidraw_device()


def _open_matching_transport() -> tuple[HidrawFeatureOutputTransport, HidrawDeviceInfo]:
    return open_matching_hidraw_transport()


def _identifiers_for_match(match: HidrawDeviceInfo) -> dict[str, str]:
    identifiers = {
        "usb_vid": f"0x{int(match.vendor_id):04x}",
        "usb_pid": f"0x{int(match.product_id):04x}",
        "hidraw": str(match.devnode),
    }
    if match.hid_name:
        identifiers["hid_name"] = str(match.hid_name)
    if match.bcd_device is not None:
        identifiers["usb_bcd_device"] = f"0x{int(match.bcd_device):04x}"
    return identifiers


@dataclass
class Ite8291Backend(KeyboardBackend):
    """Experimental native HID backend for the ITE 8291 6x21 row protocol."""

    name: str = "ite8291"
    priority: int = 97
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS),
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8291 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return ProbeResult(
                available=False,
                reason=(
                    "no matching hidraw device for experimental ITE 8291 IDs: "
                    + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS)
                ),
                confidence=0,
                identifiers=identifiers,
            )

        identifiers = _identifiers_for_match(match)

        if protocol.firmware_requires_zone_mode(match.product_id, match.bcd_device):
            return ProbeResult(
                available=False,
                reason=(
                    "detected legacy ITE 8291 zone-only firmware variant "
                    f"(0x{int(match.vendor_id):04x}:0x{int(match.product_id):04x}, "
                    f"bcdDevice 0x{int(match.bcd_device or 0):04x}) which is not implemented by this per-key backend"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        if not experimental_backends_enabled():
            return ProbeResult(
                available=False,
                reason=(
                    "experimental backend disabled (detected "
                    f"0x{int(match.vendor_id):04x}:0x{int(match.product_id):04x}; "
                    "enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        return ProbeResult(
            available=True,
            reason=f"hidraw device present ({match.devnode})",
            confidence=82,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=True, color=True, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8291 native HID support is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, info = _open_matching_transport()
            if protocol.firmware_requires_zone_mode(info.product_id, info.bcd_device):
                raise RuntimeError(
                    "Detected an ITE 8291 zone-only firmware variant; the experimental per-key HID backend does not support it yet."
                )
            return Ite8291KeyboardDevice(transport.send_feature_report, transport.write_output_report)
        except BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if is_permission_denied(exc):
                raise BackendPermissionError(
                    "Permission denied opening the ITE 8291 hidraw device. Install the KeyRGB udev rules, then reload "
                    "udev or reboot/log out and back in."
                ) from exc
            if is_device_disconnected(exc):
                raise BackendDisconnectedError("ITE 8291 device disconnected during initialization") from exc
            if is_device_busy(exc):
                raise BackendBusyError("ITE 8291 device is busy; another process may own it") from exc
            if isinstance(exc, RuntimeError):
                raise
            raise BackendIOError(f"ITE 8291 HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (protocol.NUM_ROWS, protocol.NUM_COLS)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
