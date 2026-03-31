from __future__ import annotations

import os
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from src.core.utils.exceptions import is_permission_denied

from ..base import BackendCapabilities, BackendStability, KeyboardBackend, KeyboardDevice, ProbeResult
from .device import Ite8910KeyboardDevice
from .hidraw import find_matching_hidraw_device, open_matching_hidraw_transport
from . import protocol


def _effect_builder(effect_name: str, *, extra: tuple[str, ...] = ()) -> Callable[..., dict[str, Any]]:
    args = {"speed": None, "brightness": None}
    for k in extra:
        args[k] = None

    def build(**kwargs: Any) -> dict[str, Any]:
        _ = args
        for key in kwargs:
            if key not in args:
                raise ValueError(f"'{key}' attr is not needed by effect")
        payload: dict[str, Any] = {"name": effect_name}
        payload.update(kwargs)
        return payload

    return build


@dataclass
class Ite8910Backend(KeyboardBackend):
    """Backend for the ITE 8910 HID protocol (reverse-engineered, hardware-validated)."""

    name: str = "ite8910"
    priority: int = 94
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: None = None

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return ProbeResult(
                available=False,
                reason="ite8910 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
            )

        match = find_matching_hidraw_device(protocol.VENDOR_ID, protocol.PRODUCT_ID)
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

        return ProbeResult(
            available=True,
            reason=f"hidraw device present ({match.devnode})",
            confidence=88,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=False)

    def get_device(self) -> KeyboardDevice:
        try:
            transport, _info = open_matching_hidraw_transport(protocol.VENDOR_ID, protocol.PRODUCT_ID)
            return Ite8910KeyboardDevice(transport.send_feature_report)
        except Exception as exc:
            if is_permission_denied(exc):
                raise PermissionError(
                    "Permission denied opening the ITE 8910 hidraw device. "
                    "Install the KeyRGB udev rules, then reload udev or reboot/log out and back in."
                ) from exc
            raise

    def dimensions(self) -> tuple[int, int]:
        return (protocol.NUM_ROWS, protocol.NUM_COLS)

    def effects(self) -> dict[str, Any]:
        return {
            "rainbow": _effect_builder("rainbow_wave"),
            "breathing": _effect_builder("breathing_color", extra=("color",)),
            "wave": _effect_builder("rainbow_wave", extra=("direction", "color")),
            "scan": _effect_builder("scan", extra=("color",)),
            "flashing": _effect_builder("flashing_color", extra=("color",)),
            "random": _effect_builder("random_color", extra=("color",)),
            "snake": _effect_builder("snake", extra=("direction", "color")),
            "spectrum_cycle": _effect_builder("spectrum_cycle"),
        }

    def colors(self) -> dict[str, Any]:
        return {}
