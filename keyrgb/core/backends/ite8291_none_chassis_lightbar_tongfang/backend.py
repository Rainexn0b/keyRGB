from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import base
from ..policies.backend_selection import experimental_backends_enabled
from ..shared_hidraw_probe import (
    find_matching_ite8291_style_hidraw_device,
    identifiers_for_hidraw_match,
    open_matching_ite8291_style_hidraw_transport,
)
from . import protocol

if TYPE_CHECKING:
    from ..ite8291_perkey import hidraw

BACKEND_NAME = "ite8291_none_chassis_lightbar_tongfang"


def _find_matching_supported_hidraw_device() -> hidraw.HidrawDeviceInfo | None:
    return find_matching_ite8291_style_hidraw_device(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _open_matching_transport() -> tuple[hidraw.HidrawFeatureOutputTransport, hidraw.HidrawDeviceInfo]:
    return open_matching_ite8291_style_hidraw_transport(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
        backend_name=BACKEND_NAME,
        vendor_id=protocol.VENDOR_ID,
        missing_label="ITE 8291 Tongfang lightbar",
    )


@dataclass
class Ite8291TongfangLightbarBackend(base.KeyboardBackend):
    """Experimental auxiliary lightbar backend for 048d:6005 (Tongfang).

    OpenRGB ``IonicoController`` evidence; expected usage page ``0xFF03`` /
    usage ``0x01`` below is detector metadata only and is not claimed to have
    been verified against sysfs HID descriptors on real hardware.
    """

    name: str = BACKEND_NAME
    priority: int = 96
    stability: base.BackendStability = base.BackendStability.EXPERIMENTAL
    experimental_evidence: base.ExperimentalEvidence = base.ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> base.ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{product_id:04x}" for product_id in protocol.SUPPORTED_PRODUCT_IDS),
            "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
            "usage": f"0x{protocol.USAGE:02x}",
            "feature_report_size": str(protocol.FEATURE_REPORT_LENGTH),
            "output_report_size": str(protocol.OUTPUT_REPORT_LENGTH),
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return base.ProbeResult(
                available=False,
                reason=f"{BACKEND_NAME} hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return base.ProbeResult(
                available=False,
                reason=(
                    "no matching hidraw device for ITE 8291 Tongfang lightbar IDs: "
                    + ", ".join(
                        f"0x{protocol.VENDOR_ID:04x}:0x{product_id:04x}"
                        for product_id in protocol.SUPPORTED_PRODUCT_IDS
                    )
                ),
                confidence=0,
                identifiers=identifiers,
            )

        identifiers = identifiers_for_hidraw_match(match)
        identifiers.update(
            {
                "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
                "usage": f"0x{protocol.USAGE:02x}",
                "feature_report_size": str(protocol.FEATURE_REPORT_LENGTH),
                "output_report_size": str(protocol.OUTPUT_REPORT_LENGTH),
            }
        )

        if not experimental_backends_enabled():
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
            reason=f"hidraw lightbar device present ({match.devnode})",
            confidence=83,
            identifiers=identifiers,
        )

    def capabilities(self) -> base.BackendCapabilities:
        # Hardware effects are implemented on the device but conservatively
        # unadvertised: the secondary UI does not expose/validate them yet.
        return base.BackendCapabilities(
            brightness=True,
            per_key=False,
            color=True,
            hardware_effects=False,
            palette=False,
        )

    def get_device(self) -> base.KeyboardDevice:
        import keyrgb.core.backends.exceptions as backend_exceptions
        import keyrgb.core.utils.exceptions as core_exceptions

        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8291 Tongfang lightbar support is classified as experimental. Enable Experimental backends "
                "in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, info = _open_matching_transport()
            from .device import Ite8291TongfangLightbarDevice

            return Ite8291TongfangLightbarDevice(
                transport.send_feature_report,
                transport.write_output_report,
                product_id=int(info.product_id),
                transport=transport,
            )
        except backend_exceptions.BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if core_exceptions.is_permission_denied(exc):
                raise backend_exceptions.BackendPermissionError(
                    "Permission denied opening the ITE 8291 Tongfang lightbar hidraw device. "
                    "Install the KeyRGB udev rules, then reload udev or reboot/log out and back in."
                ) from exc
            if core_exceptions.is_device_disconnected(exc):
                raise backend_exceptions.BackendDisconnectedError(
                    "ITE 8291 Tongfang lightbar device disconnected during initialization"
                ) from exc
            if core_exceptions.is_device_busy(exc):
                raise backend_exceptions.BackendBusyError(
                    "ITE 8291 Tongfang lightbar device is busy; another process may own it"
                ) from exc
            raise backend_exceptions.BackendIOError(f"ITE 8291 Tongfang lightbar HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (1, protocol.DECLARED_LED_COUNT)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
