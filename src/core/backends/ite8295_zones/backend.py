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
from .device import Ite8295ZonesKeyboardDevice


def _find_matching_supported_hidraw_device() -> HidrawDeviceInfo | None:
    return find_matching_hidraw_device(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _open_matching_transport() -> tuple[HidrawFeatureOutputTransport, HidrawDeviceInfo]:
    return open_matching_hidraw_transport(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _effect_builder(effect_name: str, *, extra: tuple[str, ...] = ()):
    args = {"speed": None, "brightness": None}
    for key in extra:
        args[key] = None

    def build(**kwargs: object) -> dict[str, object]:
        _ = args
        for key in kwargs:
            if key not in args:
                raise ValueError(f"'{key}' attr is not needed by effect")
        payload: dict[str, object] = {"name": effect_name}
        payload.update(kwargs)
        return payload

    return build


@dataclass
class Ite8295ZonesBackend(KeyboardBackend):
    """Experimental Lenovo 4-zone ITE 8295 hidraw backend for 0x048d:0xc963."""

    name: str = "ite8295-zones"
    priority: int = 97
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{product_id:04x}" for product_id in protocol.SUPPORTED_PRODUCT_IDS),
            "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
            "usage": f"0x{protocol.USAGE:04x}",
            "feature_report_size": str(protocol.PACKET_SIZE),
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8295-zones hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return ProbeResult(
                available=False,
                reason="no matching hidraw device for Lenovo 4-zone ITE 8295 path",
                confidence=0,
                identifiers=identifiers,
            )

        identifiers = {
            "usb_vid": f"0x{int(match.vendor_id):04x}",
            "usb_pid": f"0x{int(match.product_id):04x}",
            "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
            "usage": f"0x{protocol.USAGE:04x}",
            "feature_report_size": str(protocol.PACKET_SIZE),
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
            reason=f"hidraw Lenovo 4-zone keyboard present ({match.devnode})",
            confidence=82,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, color=True, hardware_effects=True, palette=False)

    def get_device(self) -> KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8295 4-zone support is classified as experimental. Enable Experimental backends in Settings or "
                "set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            return Ite8295ZonesKeyboardDevice(transport.send_feature_report)
        except BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if is_permission_denied(exc):
                raise BackendPermissionError(
                    "Permission denied opening the ITE 8295 4-zone hidraw device. Install the KeyRGB udev rules, then "
                    "reload udev or reboot/log out and back in."
                ) from exc
            if is_device_disconnected(exc):
                raise BackendDisconnectedError("ITE 8295 4-zone device disconnected during initialization") from exc
            if is_device_busy(exc):
                raise BackendBusyError("ITE 8295 4-zone device is busy; another process may own it") from exc
            if isinstance(exc, RuntimeError):
                raise
            raise BackendIOError(f"ITE 8295 4-zone HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (1, protocol.NUM_ZONES)

    def effects(self) -> dict[str, Any]:
        return {
            "breathing": _effect_builder("breathing", extra=("color",)),
            "wave": _effect_builder("wave", extra=("direction",)),
            "spectrum_cycle": _effect_builder("spectrum_cycle"),
        }

    def colors(self) -> dict[str, Any]:
        return {}
