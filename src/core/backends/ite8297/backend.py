from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import src.core.backends.exceptions as backend_exceptions
import src.core.utils.exceptions as device_error_checks

from .. import base, policy
from ..ite8910 import hidraw as ite8910_hidraw
from . import device, protocol


find_matching_hidraw_device = ite8910_hidraw.find_matching_hidraw_device


def _find_matching_supported_hidraw_device() -> ite8910_hidraw.HidrawDeviceInfo | None:
    forced_path = os.environ.get(protocol.HIDRAW_PATH_ENV)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return ite8910_hidraw.HidrawDeviceInfo(
                hidraw_name=devnode.name,
                devnode=devnode,
                sysfs_dir=Path(),
                vendor_id=protocol.VENDOR_ID,
                product_id=protocol.SUPPORTED_PRODUCT_IDS[0],
                hid_id=f"forced:{protocol.VENDOR_ID:04x}:{protocol.SUPPORTED_PRODUCT_IDS[0]:04x}",
            )

    for product_id in protocol.SUPPORTED_PRODUCT_IDS:
        match = find_matching_hidraw_device(protocol.VENDOR_ID, product_id)
        if match is not None:
            return match

    return None


def _open_matching_transport() -> tuple[
    ite8910_hidraw.HidrawFeatureTransport,
    ite8910_hidraw.HidrawDeviceInfo,
]:
    info = _find_matching_supported_hidraw_device()
    if info is None:
        raise FileNotFoundError(
            "No hidraw device found for supported ITE 8297 controller IDs: "
            + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS)
        )
    return ite8910_hidraw.HidrawFeatureTransport(info.devnode), info


@dataclass
class Ite8297Backend(base.KeyboardBackend):
    """Experimental ITE 8297 backend for the public 64-byte uniform-color HID path.

    This implementation is intentionally conservative: it only enables the
    confirmed `0x048d:0x8297` path and exposes uniform color writes, not per-key
    control or firmware effects.
    """

    name: str = "ite8297"
    priority: int = 95
    stability: base.BackendStability = base.BackendStability.EXPERIMENTAL
    experimental_evidence: base.ExperimentalEvidence = base.ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> base.ProbeResult:
        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return base.ProbeResult(
                available=False,
                reason="ite8297 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return base.ProbeResult(
                available=False,
                reason="no matching hidraw device",
                confidence=0,
            )

        identifiers = {
            "usb_vid": f"0x{int(match.vendor_id):04x}",
            "usb_pid": f"0x{int(match.product_id):04x}",
            "hidraw": str(match.devnode),
        }
        if match.hid_name:
            identifiers["hid_name"] = str(match.hid_name)

        if not policy.experimental_backends_enabled():
            return base.ProbeResult(
                available=False,
                reason=(
                    "experimental backend disabled (detected "
                    f"0x{int(match.vendor_id):04x}:0x{int(match.product_id):04x}; "
                    "enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        return base.ProbeResult(
            available=True,
            reason=f"hidraw device present ({match.devnode})",
            confidence=84,
            identifiers=identifiers,
        )

    def capabilities(self) -> base.BackendCapabilities:
        return base.BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)

    def get_device(self) -> base.KeyboardDevice:
        if not policy.experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8297 is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            return device.Ite8297KeyboardDevice(transport.send_feature_report, transport=transport)
        except backend_exceptions.BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if device_error_checks.is_permission_denied(exc):
                raise backend_exceptions.BackendPermissionError(
                    "Permission denied opening the ITE 8297 hidraw device. "
                    "Install the KeyRGB udev rules, then reload udev or reboot/log out and back in."
                ) from exc
            if device_error_checks.is_device_disconnected(exc):
                raise backend_exceptions.BackendDisconnectedError(
                    "ITE 8297 device disconnected during initialization"
                ) from exc
            if device_error_checks.is_device_busy(exc):
                raise backend_exceptions.BackendBusyError(
                    "ITE 8297 device is busy; another process may own it"
                ) from exc
            raise backend_exceptions.BackendIOError(f"ITE 8297 HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (1, 1)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
