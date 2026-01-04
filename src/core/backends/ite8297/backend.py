from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from ..base import BackendCapabilities, KeyboardDevice, KeyboardBackend, ProbeResult

logger = logging.getLogger(__name__)


# Intentionally empty: we do NOT enable this backend by default.
#
# Rationale:
# - There are ITE controller families (commonly described as IT8297/8176) that
#   appear to use a different HID report dialect than the IT8291r3 devices
#   supported by `src.core.backends.ite8291r3`.
# - Without hardware to validate, enabling probe/usage would be risky.
#
# When this backend is implemented and validated, add confirmed VID/PID pairs
# here and in udev rules (if applicable).
_ITE8297_USB_IDS: list[tuple[int, int]] = []



@dataclass
class Ite8297Backend(KeyboardBackend):
    """Placeholder backend for the IT8297/8176-family HID dialect.

    This backend is deliberately dormant: it never probes available unless the
    allowlist above is populated.
    """

    name: str = "ite8297"
    priority: int = 95

    def is_available(self) -> bool:
        # We consider it available only when explicitly enabled via allowlist.
        return len(_ITE8297_USB_IDS) > 0

    def probe(self) -> ProbeResult:
        if len(_ITE8297_USB_IDS) == 0:
            return ProbeResult(
                available=False,
                reason="ite8297 backend scaffold present but disabled (no confirmed USB IDs)",
                confidence=0,
            )

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=True,
                reason="enabled but usb scan disabled",
                confidence=40,
            )

        try:
            import usb.core  # type: ignore

            for vid, pid in _ITE8297_USB_IDS:
                dev = usb.core.find(idVendor=int(vid), idProduct=int(pid))
                if dev is not None:
                    return ProbeResult(
                        available=True,
                        reason=f"usb device present (0x{int(vid):04x}:0x{int(pid):04x})",
                        confidence=80,
                        identifiers={"usb_vid": f"0x{int(vid):04x}", "usb_pid": f"0x{int(pid):04x}"},
                    )

            return ProbeResult(available=False, reason="no matching usb device", confidence=0)
        except Exception as exc:
            return ProbeResult(available=True, reason=f"enabled but usb scan unavailable: {exc}", confidence=40)

    def capabilities(self) -> BackendCapabilities:
        # Unknown until implemented; keep conservative.
        return BackendCapabilities(per_key=False, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        raise NotImplementedError(
            "ITE8297 backend is a scaffold only and is not implemented yet. "
            "Do not enable it without a validated implementation and hardware testing."
        )

    def dimensions(self) -> tuple[int, int]:
        # Unknown until implemented.
        return (0, 0)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
