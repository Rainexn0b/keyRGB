from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any

from src.core.runtime.imports import ensure_ite8291r3_ctl_importable

from ..base import BackendCapabilities, KeyboardDevice, KeyboardBackend, ProbeResult

logger = logging.getLogger(__name__)

_FALLBACK_USB_IDS: list[tuple[int, int]] = [
    # WootBook / common Tongfang rebrands
    (0x048D, 0x6008),  # Generic ITE 8291 RGB Controller
    (0x048D, 0x600B),  # Newer ITE 8291 (2023+ Tongfang iterations)
]


@dataclass
class Ite8291r3Backend(KeyboardBackend):
    name: str = "ite8291r3"
    priority: int = 100

    def _import(self):
        if os.environ.get("KEYRGB_USE_INSTALLED_ITE") != "1":
            # Best-effort repo fallback for dev checkouts.
            ensure_ite8291r3_ctl_importable(__file__)

        from ite8291r3_ctl import ite8291r3  # type: ignore

        return ite8291r3

    def is_available(self) -> bool:
        try:
            self._import()
            return True
        except Exception:
            return False

    def probe(self) -> ProbeResult:
        """Probe for an ITE 8291r3-style USB keyboard controller.

        This is best-effort and designed to be safe/fast:
        - validates the Python backend can be imported
        - tries to detect a known USB VID/PID without opening the device
        """

        try:
            ite8291r3 = self._import()
        except Exception as exc:
            return ProbeResult(available=False, reason=f"import failed: {exc}", confidence=0)

        # If we can scan USB, only claim availability when a matching device exists.
        # If we cannot (or do not want to) scan USB, fall back to a lower-confidence
        # "importable" availability so users can still force it.

        # Respect global USB-scan disable flag (primarily used to keep unit tests
        # deterministic and to avoid unintended controller side effects).
        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=True,
                reason="importable but usb scan disabled",
                confidence=60,
            )
        try:
            import usb.core  # type: ignore

            vendor_id = int(getattr(ite8291r3, "VENDOR_ID", 0x048D))
            product_ids = list(getattr(ite8291r3, "PRODUCT_IDS", []) or [])
            for vid, pid in _FALLBACK_USB_IDS:
                if int(vid) == vendor_id and int(pid) not in product_ids:
                    product_ids.append(int(pid))

            for pid in product_ids:
                dev = usb.core.find(idVendor=vendor_id, idProduct=int(pid))
                if dev is not None:
                    return ProbeResult(
                        available=True,
                        reason=f"usb device present (0x{vendor_id:04x}:0x{int(pid):04x})",
                        confidence=90,
                        identifiers={"usb_vid": f"0x{vendor_id:04x}", "usb_pid": f"0x{int(pid):04x}"},
                    )

            return ProbeResult(available=False, reason="no matching usb device", confidence=0)
        except Exception as exc:
            return ProbeResult(
                available=True,
                reason=f"importable but usb scan unavailable: {exc}",
                confidence=60,
            )

    def capabilities(self) -> BackendCapabilities:
        # ITE supports per-key, HW effects, and palette programming.
        return BackendCapabilities(per_key=True, hardware_effects=True, palette=True)

    def get_device(self) -> KeyboardDevice:
        ite8291r3 = self._import()
        try:
            return ite8291r3.get()
        except Exception as exc:
            # Common failure mode: user lacks rw access to /dev/bus/usb/... for the keyboard.
            # After distro updates, udev rules can be removed/reset.
            msg = str(exc).lower()
            errno = getattr(exc, "errno", None)
            if isinstance(exc, PermissionError) or errno == 13 or "permission denied" in msg or "access denied" in msg:
                raise PermissionError(
                    "Permission denied opening the ITE 8291 USB device. "
                    "Install the udev rule (udev/99-ite8291-wootbook.rules), then reload udev rules and reboot/log out/in."
                ) from exc
            if os.environ.get("KEYRGB_DEBUG"):
                logger.exception("Failed to open ite8291r3 device")
            raise

    def dimensions(self) -> tuple[int, int]:
        ite8291r3 = self._import()
        return int(ite8291r3.NUM_ROWS), int(ite8291r3.NUM_COLS)

    def effects(self) -> dict[str, Any]:
        ite8291r3 = self._import()
        return dict(getattr(ite8291r3, "effects", {}) or {})

    def colors(self) -> dict[str, Any]:
        ite8291r3 = self._import()
        return dict(getattr(ite8291r3, "colors", {}) or {})
