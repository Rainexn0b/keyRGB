from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from src.core.utils.exceptions import is_permission_denied

from ..base import BackendCapabilities, BackendStability, ExperimentalEvidence, KeyboardDevice, KeyboardBackend, ProbeResult
from ..ite8910.hidraw import HidrawDeviceInfo, HidrawFeatureTransport, find_matching_hidraw_device
from ..policy import experimental_backends_enabled
from .device import Ite8297KeyboardDevice
from . import protocol


def _find_matching_supported_hidraw_device() -> HidrawDeviceInfo | None:
    forced_path = os.environ.get(protocol.HIDRAW_PATH_ENV)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return HidrawDeviceInfo(
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


def _open_matching_transport() -> tuple[HidrawFeatureTransport, HidrawDeviceInfo]:
    info = _find_matching_supported_hidraw_device()
    if info is None:
        raise FileNotFoundError(
            "No hidraw device found for supported ITE 8297 controller IDs: "
            + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS)
        )
    return HidrawFeatureTransport(info.devnode), info


@dataclass
class Ite8297Backend(KeyboardBackend):
    """Experimental ITE 8297 backend for the public 64-byte uniform-color HID path.

    This implementation is intentionally conservative: it only enables the
    confirmed `0x048d:0x8297` path and exposes uniform color writes, not per-key
    control or firmware effects.
    """

    name: str = "ite8297"
    priority: int = 95
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8297 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return ProbeResult(
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
            confidence=84,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8297 is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            return Ite8297KeyboardDevice(transport.send_feature_report)
        except Exception as exc:
            if is_permission_denied(exc):
                raise PermissionError(
                    "Permission denied opening the ITE 8297 hidraw device. "
                    "Install the KeyRGB udev rules, then reload udev or reboot/log out and back in."
                ) from exc
            raise

    def dimensions(self) -> tuple[int, int]:
        return (1, 1)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
