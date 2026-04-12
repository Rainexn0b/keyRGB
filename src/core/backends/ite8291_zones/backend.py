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
from ..ite8291.hidraw import (
    HidrawDeviceInfo,
    HidrawFeatureOutputTransport,
    find_matching_hidraw_device,
    open_matching_hidraw_transport,
)
from ..policy import experimental_backends_enabled
from . import protocol
from .device import Ite8291ZonesKeyboardDevice


def _find_matching_supported_hidraw_device() -> HidrawDeviceInfo | None:
    match = find_matching_hidraw_device(
        product_ids=(protocol.PRODUCT_ID,),
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )
    if match is None:
        return None
    if match.bcd_device is None and os.environ.get(protocol.HIDRAW_PATH_ENV):
        match = HidrawDeviceInfo(
            hidraw_name=match.hidraw_name,
            devnode=match.devnode,
            sysfs_dir=match.sysfs_dir,
            vendor_id=match.vendor_id,
            product_id=match.product_id,
            hid_id=match.hid_id,
            hid_name=match.hid_name,
            bcd_device=protocol.REQUIRED_BCD_DEVICE,
        )
    if int(match.product_id) != int(protocol.PRODUCT_ID):
        return None
    if int(match.bcd_device or 0) != int(protocol.REQUIRED_BCD_DEVICE):
        return None
    return match


def _open_matching_transport() -> tuple[HidrawFeatureOutputTransport, HidrawDeviceInfo]:
    transport, info = open_matching_hidraw_transport(
        product_ids=(protocol.PRODUCT_ID,),
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )
    if int(info.bcd_device or 0) != int(protocol.REQUIRED_BCD_DEVICE):
        transport.close()
        raise RuntimeError(
            "Detected ITE 8291 ce00 firmware, but it is not the supported 4-zone bcdDevice 0x0002 variant."
        )
    return transport, info


@dataclass
class Ite8291ZonesBackend(KeyboardBackend):
    """Experimental 4-zone backend for the legacy ITE 8291 ce00 firmware split."""

    name: str = "ite8291-zones"
    priority: int = 96
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": f"0x{protocol.PRODUCT_ID:04x}",
            "usb_bcd_device": f"0x{protocol.REQUIRED_BCD_DEVICE:04x}",
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8291-zones hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return ProbeResult(
                available=False,
                reason=(
                    "no matching hidraw device for experimental ITE 8291 4-zone firmware "
                    f"(0x{protocol.VENDOR_ID:04x}:0x{protocol.PRODUCT_ID:04x}, bcdDevice 0x{protocol.REQUIRED_BCD_DEVICE:04x})"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        identifiers = {
            "usb_vid": f"0x{int(match.vendor_id):04x}",
            "usb_pid": f"0x{int(match.product_id):04x}",
            "usb_bcd_device": f"0x{int(match.bcd_device or 0):04x}",
            "hidraw": str(match.devnode),
        }
        if match.hid_name:
            identifiers["hid_name"] = str(match.hid_name)

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
            reason=f"hidraw 4-zone device present ({match.devnode})",
            confidence=80,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8291 4-zone support is classified as experimental. Enable Experimental backends in Settings or "
                "set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            return Ite8291ZonesKeyboardDevice(transport.send_feature_report)
        except BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if is_permission_denied(exc):
                raise BackendPermissionError(
                    "Permission denied opening the ITE 8291 4-zone hidraw device. Install the KeyRGB udev rules, then "
                    "reload udev or reboot/log out and back in."
                ) from exc
            if is_device_disconnected(exc):
                raise BackendDisconnectedError("ITE 8291 4-zone device disconnected during initialization") from exc
            if is_device_busy(exc):
                raise BackendBusyError("ITE 8291 4-zone device is busy; another process may own it") from exc
            if isinstance(exc, RuntimeError):
                raise
            raise BackendIOError(f"ITE 8291 4-zone HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (1, protocol.NUM_ZONES)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
