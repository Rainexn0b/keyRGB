from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..base import (
    BackendCapabilities,
    BackendStability,
    ExperimentalEvidence,
    KeyboardDevice,
    KeyboardBackend,
    ProbeResult,
)
from ..policy import experimental_backends_enabled
from . import protocol

if TYPE_CHECKING:
    from ..ite8910.hidraw import HidrawDeviceInfo, HidrawFeatureTransport


def _hidraw_module() -> Any:
    # Keep hidraw dependency lazy to avoid pulling USB internals during backend discovery import.
    from ..ite8910 import hidraw

    return hidraw


def find_matching_hidraw_device(
    vendor_id: int,
    product_id: int,
    *,
    root: Path | None = None,
    dev_root: Path | None = None,
) -> HidrawDeviceInfo | None:
    hidraw = _hidraw_module()
    return hidraw.find_matching_hidraw_device(vendor_id, product_id, root=root, dev_root=dev_root)


def _forced_hidraw_device_info(devnode: Path) -> HidrawDeviceInfo:
    hidraw = _hidraw_module()
    return hidraw.HidrawDeviceInfo(
        hidraw_name=devnode.name,
        devnode=devnode,
        sysfs_dir=Path(),
        vendor_id=protocol.VENDOR_ID,
        product_id=protocol.DEFAULT_PRODUCT_ID,
        hid_id=f"forced:{protocol.VENDOR_ID:04x}:{protocol.DEFAULT_PRODUCT_ID:04x}",
    )


def _find_matching_supported_hidraw_device() -> HidrawDeviceInfo | None:
    forced_path = os.environ.get(protocol.HIDRAW_PATH_ENV)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return _forced_hidraw_device_info(devnode)

    for product_id in protocol.SUPPORTED_PRODUCT_IDS:
        match = find_matching_hidraw_device(protocol.VENDOR_ID, product_id)
        if match is not None:
            return match

    return None


def _open_matching_transport() -> tuple[HidrawFeatureTransport, HidrawDeviceInfo]:
    hidraw = _hidraw_module()
    info = _find_matching_supported_hidraw_device()
    if info is None:
        raise FileNotFoundError(
            "No hidraw device found for supported ITE 8233 lightbar IDs: "
            + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS)
        )
    return hidraw.HidrawFeatureTransport(info.devnode), info


@dataclass
class Ite8233Backend(KeyboardBackend):
    """Experimental ITE lightbar backend for the vendor-backed 0x7000/0x7001 HID path."""

    name: str = "ite8233"
    priority: int = 96
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{product_id:04x}" for product_id in protocol.SUPPORTED_PRODUCT_IDS),
            "feature_report_id": f"0x{protocol.FEATURE_REPORT_ID:02x}",
            "feature_report_size": str(protocol.FEATURE_REPORT_SIZE),
            "usage_page": f"0x{protocol.VENDOR_USAGE_PAGE:04x}",
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8233 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return ProbeResult(
                available=False,
                reason=(
                    "no matching hidraw device for speculative ITE lightbar IDs: "
                    + ", ".join(
                        f"0x{protocol.VENDOR_ID:04x}:0x{product_id:04x}"
                        for product_id in protocol.SUPPORTED_PRODUCT_IDS
                    )
                ),
                confidence=0,
                identifiers=identifiers,
            )

        identifiers.update(
            {
                "usb_vid": f"0x{match.vendor_id:04x}",
                "usb_pid": f"0x{match.product_id:04x}",
                "hidraw": str(match.devnode),
                "hid_id": str(match.hid_id or ""),
                "hid_name": str(match.hid_name or ""),
            }
        )

        if not experimental_backends_enabled():
            return ProbeResult(
                available=False,
                reason=(
                    "experimental backend disabled (detected "
                    f"0x{match.vendor_id:04x}:0x{match.product_id:04x}; "
                    "enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        return ProbeResult(
            available=True,
            reason=f"hidraw lightbar device present ({match.devnode})",
            confidence=83,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            per_key=False,
            color=True,
            hardware_effects=False,
            palette=False,
        )

    def get_device(self) -> KeyboardDevice:
        import src.core.backends.exceptions as backend_exceptions
        import src.core.utils.exceptions as core_exceptions

        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8233 is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, info = _open_matching_transport()
            from .device import Ite8233LightbarDevice

            return Ite8233LightbarDevice(transport.send_feature_report, product_id=int(info.product_id))
        except backend_exceptions.BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if core_exceptions.is_permission_denied(exc):
                raise backend_exceptions.BackendPermissionError(
                    "Permission denied opening the ITE 8233 hidraw device. "
                    "Install the KeyRGB udev rules, then reload udev or reboot/log out and back in."
                ) from exc
            if core_exceptions.is_device_disconnected(exc):
                raise backend_exceptions.BackendDisconnectedError(
                    "ITE 8233 device disconnected during initialization"
                ) from exc
            if core_exceptions.is_device_busy(exc):
                raise backend_exceptions.BackendBusyError(
                    "ITE 8233 device is busy; another process may own it"
                ) from exc
            raise backend_exceptions.BackendIOError(f"ITE 8233 HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (1, 1)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
