from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.core.utils.exceptions import is_permission_denied

from ..base import BackendCapabilities, BackendStability, KeyboardBackend, KeyboardDevice, ProbeResult
from ..policy import experimental_backends_enabled
from .device import Ite8910KeyboardDevice
from .hidraw import find_matching_hidraw_device, open_matching_hidraw_transport
from . import protocol


def _effect_builder(effect_name: str):
    args = {"speed": None, "brightness": None}

    def build(**kwargs):
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
    """Experimental backend for the translated ITE 8910 / 829x protocol."""

    name: str = "ite8910"
    priority: int = 94
    stability: BackendStability = BackendStability.EXPERIMENTAL

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

        if not experimental_backends_enabled():
            return ProbeResult(
                available=False,
                reason=(
                    "experimental backend disabled (detected 0x048d:0x8910; "
                    "enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        return ProbeResult(
            available=True,
            reason=f"hidraw device present ({match.devnode})",
            confidence=88,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=False)

    def get_device(self) -> KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8910 is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

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
        return {name: _effect_builder(name) for name in protocol.CANONICAL_EFFECTS}

    def colors(self) -> dict[str, Any]:
        return {}