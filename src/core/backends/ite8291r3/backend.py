from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from src.core.runtime.imports import ensure_ite8291r3_ctl_importable
from src.core.utils.exceptions import is_device_busy, is_device_disconnected, is_permission_denied
from src.core.backends.exceptions import (
    BackendBusyError,
    BackendDisconnectedError,
    BackendIOError,
    BackendPermissionError,
)

from ..base import BackendCapabilities, BackendStability, KeyboardBackend, KeyboardDevice, ProbeResult

logger = logging.getLogger(__name__)

_ITE_IMPORT_ERRORS = (ImportError, OSError, RuntimeError, SyntaxError, ValueError)
_DEVICE_TAG_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)
_USB_SCAN_VALUE_ERRORS = (OverflowError, TypeError, ValueError)

_FALLBACK_USB_IDS: list[tuple[int, int]] = [
    # WootBook / common Tongfang rebrands
    # Also includes the upstream ite8291r3-ctl set (6004/6006/600b/ce00) so we
    # can still probe correctly even if a distro-packaged version is older.
    (0x048D, 0x6004),
    (0x048D, 0x6006),
    (0x048D, 0x6008),  # Generic ITE 8291 RGB Controller
    (0x048D, 0x600A),  # ITE 8291 (Tuxedo/Clevo variants)
    (0x048D, 0x600B),  # Newer ITE 8291 (2023+ Tongfang iterations)
    (0x048D, 0xCE00),
]

# Known ITE controllers seen in the wild that appear to be a different protocol
# family (often referred to as "Fusion 2" in community tooling).
#
# Safety: keyrgb does NOT claim support for these by adding them to PRODUCT_IDS,
# otherwise auto-selection may pick this backend and attempt to talk the wrong
# protocol to the device.
_KNOWN_UNSUPPORTED_USB_IDS: list[tuple[int, int]] = [
    (0x048D, 0x8297),  # ITE 8297 (Gigabyte/Tongfang)
    (0x048D, 0x5702),  # ITE 5702 (Gigabyte)
    # Reported in the wild as an ITE 8297/8176-family controller using a
    # different HID report dialect than 8291r3. Treat as unsupported until we
    # have a dedicated backend + hardware confirmation.
    (0x048D, 0xC966),
]


class _Ite8291r3ModuleProtocol(Protocol):
    VENDOR_ID: int
    PRODUCT_IDS: list[int]
    NUM_ROWS: int
    NUM_COLS: int
    effects: Mapping[str, object]
    colors: Mapping[str, object]
    usb: object

    def get(self) -> KeyboardDevice: ...


def _usb_runtime_error_types(usb_core: object) -> tuple[type[BaseException], ...]:
    error_types: list[type[BaseException]] = [AttributeError, OSError, RuntimeError]
    for name in ("USBError", "NoBackendError"):
        err_type = getattr(usb_core, name, None)
        if isinstance(err_type, type) and issubclass(err_type, BaseException):
            error_types.append(err_type)
    return tuple(dict.fromkeys(error_types))


def _ite_device_open_error_types(ite8291r3: _Ite8291r3ModuleProtocol) -> tuple[type[BaseException], ...]:
    error_types: list[type[BaseException]] = [FileNotFoundError, OSError, RuntimeError, ValueError]
    usb_pkg = getattr(ite8291r3, "usb", None)
    usb_core = getattr(usb_pkg, "core", None)
    if usb_core is not None:
        error_types.extend(_usb_runtime_error_types(usb_core))
    return tuple(dict.fromkeys(error_types))


def _set_best_effort_device_attr(device: object, name: str, value: str) -> None:
    try:
        setattr(device, name, value)
    except _DEVICE_TAG_ERRORS:
        return


@dataclass
class Ite8291r3Backend(KeyboardBackend):
    name: str = "ite8291r3"
    priority: int = 100
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: None = None

    def _import(self) -> _Ite8291r3ModuleProtocol:
        if os.environ.get("KEYRGB_USE_INSTALLED_ITE") != "1":
            # Best-effort repo fallback for dev checkouts.
            ensure_ite8291r3_ctl_importable(__file__)

        from ite8291r3_ctl import ite8291r3  # type: ignore

        # Patch missing IDs into the library instance in-memory; this ensures get() works
        # even if the underlying library is old or came from a distro package.
        library_pids = getattr(ite8291r3, "PRODUCT_IDS", None)
        if isinstance(library_pids, list):
            for _, pid in _FALLBACK_USB_IDS:
                if pid not in library_pids:
                    library_pids.append(pid)

        return cast(_Ite8291r3ModuleProtocol, ite8291r3)

    def is_available(self) -> bool:
        try:
            self._import()
            return True
        except _ITE_IMPORT_ERRORS:
            return False

    def probe(self) -> ProbeResult:
        """Probe for an ITE 8291r3-style USB keyboard controller.

        This is best-effort and designed to be safe/fast:
        - validates the Python backend can be imported
        - tries to detect a known USB VID/PID without opening the device
        """

        try:
            ite8291r3 = self._import()
        except _ITE_IMPORT_ERRORS as exc:
            return ProbeResult(available=False, reason=f"import failed: {exc}", confidence=0)

        # Respect global USB-scan disable flag (primarily used to keep unit tests
        # deterministic and to avoid unintended controller side effects).
        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=True,
                reason="importable but usb scan disabled",
                confidence=60,
            )

        try:
            import usb.core as usb_core  # type: ignore
        except ImportError as exc:
            return ProbeResult(
                available=True,
                reason=f"importable but usb scan unavailable: {exc}",
                confidence=60,
            )

        scan_error_types = _usb_runtime_error_types(usb_core) + _USB_SCAN_VALUE_ERRORS
        try:
            vendor_id = int(getattr(ite8291r3, "VENDOR_ID", 0x048D))
            product_ids = list(getattr(ite8291r3, "PRODUCT_IDS", []) or [])
            for vid, pid in _FALLBACK_USB_IDS:
                if int(vid) == vendor_id and int(pid) not in product_ids:
                    product_ids.append(int(pid))

            # If we detect an ITE controller known to be a different protocol
            # family, return a *negative* probe with identifiers so debug logs
            # can guide future expansion without risking accidental usage.
            for vid, pid in _KNOWN_UNSUPPORTED_USB_IDS:
                if int(vid) != vendor_id:
                    continue
                dev = usb_core.find(idVendor=vendor_id, idProduct=int(pid))
                if dev is not None:
                    return ProbeResult(
                        available=False,
                        reason=(
                            "usb device present but unsupported by ite8291r3 backend "
                            f"(0x{vendor_id:04x}:0x{int(pid):04x})"
                        ),
                        confidence=0,
                        identifiers={
                            "usb_vid": f"0x{vendor_id:04x}",
                            "usb_pid": f"0x{int(pid):04x}",
                        },
                    )

            for pid in product_ids:
                dev = usb_core.find(idVendor=vendor_id, idProduct=int(pid))
                if dev is not None:
                    return ProbeResult(
                        available=True,
                        reason=f"usb device present (0x{vendor_id:04x}:0x{int(pid):04x})",
                        confidence=90,
                        identifiers={
                            "usb_vid": f"0x{vendor_id:04x}",
                            "usb_pid": f"0x{int(pid):04x}",
                        },
                    )

            return ProbeResult(available=False, reason="no matching usb device", confidence=0)
        except scan_error_types as exc:
            return ProbeResult(
                available=True,
                reason=f"importable but usb scan unavailable: {exc}",
                confidence=60,
            )

    def capabilities(self) -> BackendCapabilities:
        # ITE supports per-key, HW effects, and palette programming.
        return BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=True)

    def get_device(self) -> KeyboardDevice:
        ite8291r3 = self._import()
        open_error_types = _ite_device_open_error_types(ite8291r3)
        try:
            device = ite8291r3.get()
        except open_error_types as exc:
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
                logger.exception("Failed to open ite8291r3 device")
            raise BackendIOError(f"ITE 8291 USB device open failed: {exc}") from exc

        _set_best_effort_device_attr(device, "keyrgb_hw_speed_policy", "inverted")
        _set_best_effort_device_attr(device, "keyrgb_per_key_mode_policy", "reassert_every_frame")
        return device

    def dimensions(self) -> tuple[int, int]:
        ite8291r3 = self._import()
        return int(ite8291r3.NUM_ROWS), int(ite8291r3.NUM_COLS)

    def effects(self) -> dict[str, object]:
        ite8291r3 = self._import()
        return dict(getattr(ite8291r3, "effects", {}) or {})

    def colors(self) -> dict[str, object]:
        ite8291r3 = self._import()
        return dict(getattr(ite8291r3, "colors", {}) or {})
