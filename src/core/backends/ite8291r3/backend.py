from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from src.core.backends.exceptions import (
    BackendBusyError,
    BackendDisconnectedError,
    BackendIOError,
    BackendPermissionError,
)
from src.core.utils.exceptions import is_device_busy, is_device_disconnected, is_permission_denied

from ..base import BackendCapabilities, BackendStability, KeyboardBackend, KeyboardDevice, ProbeResult
from . import protocol
from .device import Ite8291r3KeyboardDevice
from .usb import device_bcd_device_or_none, open_matching_transport

logger = logging.getLogger(__name__)

_ITE_IMPORT_ERRORS = (ImportError, OSError, RuntimeError, SyntaxError, ValueError)
_DEVICE_TAG_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)
_USB_SCAN_VALUE_ERRORS = (OverflowError, TypeError, ValueError)

_SUPPORTED_USB_IDS: list[tuple[int, int]] = [(int(protocol.VENDOR_ID), int(pid)) for pid in protocol.PRODUCT_IDS]

_KNOWN_UNSUPPORTED_USB_IDS: list[tuple[int, int]] = [
    (0x048D, 0x8297),
    (0x048D, 0x5702),
    (0x048D, 0xC966),
]

_KNOWN_UNSUPPORTED_USB_BCD_VARIANTS: dict[tuple[int, int, int], str] = {
    (0x048D, 0xCE00, 0x0002): "legacy zone-only firmware variant",
}


def _load_usb_core():
    import usb.core as usb_core  # type: ignore

    return usb_core


def _usb_runtime_error_types(usb_core: object) -> tuple[type[BaseException], ...]:
    error_types: list[type[BaseException]] = [AttributeError, OSError, RuntimeError]
    for name in ("USBError", "NoBackendError"):
        err_type = getattr(usb_core, name, None)
        if isinstance(err_type, type) and issubclass(err_type, BaseException):
            error_types.append(err_type)
    return tuple(dict.fromkeys(error_types))


def _set_best_effort_device_attr(device: object, name: str, value: str) -> None:
    try:
        setattr(device, name, value)
    except _DEVICE_TAG_ERRORS:
        return


def _probe_identifiers(*, vendor_id: int, product_id: int, bcd_device: int | None = None) -> dict[str, str]:
    identifiers = {
        "usb_vid": f"0x{int(vendor_id):04x}",
        "usb_pid": f"0x{int(product_id):04x}",
    }
    if bcd_device is not None:
        identifiers["usb_bcd_device"] = f"0x{int(bcd_device):04x}"
    return identifiers


def _unsupported_variant_reason(*, vendor_id: int, product_id: int, bcd_device: int | None) -> str | None:
    if bcd_device is None:
        return None
    return _KNOWN_UNSUPPORTED_USB_BCD_VARIANTS.get((int(vendor_id), int(product_id), int(bcd_device)))


def _unexpected_revision_reason(*, bcd_device: int | None) -> str | None:
    if bcd_device is None:
        return None
    if int(bcd_device) != int(protocol.REV_NUMBER):
        return f"unexpected firmware revision 0x{int(bcd_device):04x}"
    return None


@dataclass
class Ite8291r3Backend(KeyboardBackend):
    name: str = "ite8291r3"
    priority: int = 100
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: None = None

    def _load_usb_core(self):
        return _load_usb_core()

    def is_available(self) -> bool:
        try:
            self._load_usb_core()
            return True
        except _ITE_IMPORT_ERRORS:
            return False

    def probe(self) -> ProbeResult:
        try:
            usb_core = self._load_usb_core()
        except _ITE_IMPORT_ERRORS as exc:
            return ProbeResult(available=False, reason=f"import failed: {exc}", confidence=0)

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=True,
                reason="importable but usb scan disabled",
                confidence=60,
            )

        scan_error_types = _usb_runtime_error_types(usb_core) + _USB_SCAN_VALUE_ERRORS
        try:
            vendor_id = int(protocol.VENDOR_ID)

            for vid, pid in _KNOWN_UNSUPPORTED_USB_IDS:
                if int(vid) != vendor_id:
                    continue
                dev = usb_core.find(idVendor=vendor_id, idProduct=int(pid))
                if dev is not None:
                    bcd_device = device_bcd_device_or_none(dev)
                    return ProbeResult(
                        available=False,
                        reason=(
                            "usb device present but unsupported by ite8291r3 backend "
                            f"(0x{vendor_id:04x}:0x{int(pid):04x})"
                        ),
                        confidence=0,
                        identifiers=_probe_identifiers(
                            vendor_id=vendor_id,
                            product_id=int(pid),
                            bcd_device=bcd_device,
                        ),
                    )

            for _vid, pid in _SUPPORTED_USB_IDS:
                dev = usb_core.find(idVendor=vendor_id, idProduct=int(pid))
                if dev is None:
                    continue

                bcd_device = device_bcd_device_or_none(dev)
                unsupported_variant = _unsupported_variant_reason(
                    vendor_id=vendor_id,
                    product_id=int(pid),
                    bcd_device=bcd_device,
                )
                if unsupported_variant is not None:
                    return ProbeResult(
                        available=False,
                        reason=(
                            "usb device present but unsupported by ite8291r3 backend "
                            f"(0x{vendor_id:04x}:0x{int(pid):04x}; {unsupported_variant})"
                        ),
                        confidence=0,
                        identifiers=_probe_identifiers(
                            vendor_id=vendor_id,
                            product_id=int(pid),
                            bcd_device=bcd_device,
                        ),
                    )

                unexpected_revision = _unexpected_revision_reason(bcd_device=bcd_device)
                if unexpected_revision is not None:
                    return ProbeResult(
                        available=False,
                        reason=(
                            "usb device present but unsupported by ite8291r3 backend "
                            f"(0x{vendor_id:04x}:0x{int(pid):04x}; {unexpected_revision})"
                        ),
                        confidence=0,
                        identifiers=_probe_identifiers(
                            vendor_id=vendor_id,
                            product_id=int(pid),
                            bcd_device=bcd_device,
                        ),
                    )

                return ProbeResult(
                    available=True,
                    reason=f"usb device present (0x{vendor_id:04x}:0x{int(pid):04x})",
                    confidence=90,
                    identifiers=_probe_identifiers(
                        vendor_id=vendor_id,
                        product_id=int(pid),
                        bcd_device=bcd_device,
                    ),
                )

            return ProbeResult(available=False, reason="no matching usb device", confidence=0)
        except scan_error_types as exc:
            return ProbeResult(
                available=True,
                reason=f"importable but usb scan unavailable: {exc}",
                confidence=60,
            )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=True)

    def _open_matching_transport(self):
        return open_matching_transport(product_ids=tuple(pid for _vid, pid in _SUPPORTED_USB_IDS), required_bcd=protocol.REV_NUMBER)

    def get_device(self) -> KeyboardDevice:
        try:
            usb_core = self._load_usb_core()
            transport, _info = self._open_matching_transport()
            device = Ite8291r3KeyboardDevice(
                transport.send_control_report,
                transport.read_control_report,
                transport.write_data,
            )
        except (ImportError, FileNotFoundError, OSError, RuntimeError, ValueError) as exc:  # @quality-exception exception-transparency: USB transport open is a hardware boundary; device/library failures are translated to backend errors here
            if is_permission_denied(exc):
                raise BackendPermissionError(
                    "Permission denied opening the ITE 8291 USB device. "
                    "Install the udev rule (system/udev/99-ite8291-wootbook.rules), "
                    "then reload udev rules and reboot/log out/in."
                ) from exc
            if is_device_disconnected(exc):
                raise BackendDisconnectedError("ITE 8291 device disconnected during initialization") from exc
            if is_device_busy(exc):
                raise BackendBusyError("ITE 8291 device is busy; another process may own it") from exc
            if os.environ.get("KEYRGB_DEBUG"):
                logger.exception("Failed to open native ite8291r3 device")
            raise BackendIOError(f"ITE 8291 USB device open failed: {exc}") from exc

        _set_best_effort_device_attr(device, "keyrgb_hw_speed_policy", "inverted")
        _set_best_effort_device_attr(device, "keyrgb_per_key_mode_policy", "reassert_every_frame")
        return device

    def dimensions(self) -> tuple[int, int]:
        return int(protocol.NUM_ROWS), int(protocol.NUM_COLS)

    def effects(self) -> dict[str, object]:
        return dict(protocol.effects)

    def colors(self) -> dict[str, object]:
        return dict(protocol.colors)
