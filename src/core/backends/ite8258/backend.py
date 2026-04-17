from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.backends import exceptions as backend_exceptions
from src.core.utils import exceptions as device_exception_utils

from .. import base
from ..policy import experimental_backends_enabled
from . import protocol

if TYPE_CHECKING:
    from ..ite8291 import hidraw


def _find_matching_supported_hidraw_device() -> hidraw.HidrawDeviceInfo | None:
    from ..ite8291 import hidraw

    forced_path = os.environ.get(protocol.HIDRAW_PATH_ENV)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return hidraw.HidrawDeviceInfo(
                hidraw_name=devnode.name,
                devnode=devnode,
                sysfs_dir=Path(),
                vendor_id=protocol.VENDOR_ID,
                product_id=protocol.SUPPORTED_PRODUCT_IDS[0],
                hid_id=f"forced:{protocol.VENDOR_ID:04x}:{protocol.SUPPORTED_PRODUCT_IDS[0]:04x}",
                hid_name="ITE 8258 (forced)",
            )

    return hidraw.find_matching_hidraw_device(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _open_matching_transport() -> tuple[hidraw.HidrawFeatureOutputTransport, hidraw.HidrawDeviceInfo]:
    from ..ite8291 import hidraw

    info = _find_matching_supported_hidraw_device()
    if info is None:
        raise FileNotFoundError(
            "No hidraw device found for supported ITE 8258 IDs: "
            + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS)
        )
    return hidraw.HidrawFeatureOutputTransport(info.devnode), info


def _identifiers_for_match(match: hidraw.HidrawDeviceInfo) -> dict[str, str]:
    identifiers = {
        "usb_vid": f"0x{int(match.vendor_id):04x}",
        "usb_pid": f"0x{int(match.product_id):04x}",
        "hidraw": str(match.devnode),
    }
    if match.hid_name:
        identifiers["hid_name"] = str(match.hid_name)
    return identifiers


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
class Ite8258Backend(base.KeyboardBackend):
    """Experimental 24-zone ITE 8258 hidraw backend."""

    name: str = "ite8258"
    priority: int = 98
    stability: base.BackendStability = base.BackendStability.EXPERIMENTAL
    experimental_evidence: base.ExperimentalEvidence = base.ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> base.ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS),
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return base.ProbeResult(
                available=False,
                reason="ite8258 hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
                confidence=0,
                identifiers=identifiers,
            )

        match = _find_matching_supported_hidraw_device()
        if match is None:
            return base.ProbeResult(
                available=False,
                reason="no matching hidraw device",
                confidence=0,
                identifiers=identifiers,
            )

        identifiers = _identifiers_for_match(match)

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
            reason=f"hidraw device present ({match.devnode})",
            confidence=83,
            identifiers=identifiers,
        )

    def capabilities(self) -> base.BackendCapabilities:
        return base.BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=False)

    def get_device(self) -> base.KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8258 support is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            from .device import Ite8258KeyboardDevice

            return Ite8258KeyboardDevice(transport.send_feature_report)
        except backend_exceptions.BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if device_exception_utils.is_permission_denied(exc):
                raise backend_exceptions.BackendPermissionError(
                    "Permission denied opening the ITE 8258 hidraw device. Install the KeyRGB udev rules, "
                    "then reload udev or reboot/log out and back in."
                ) from exc
            if device_exception_utils.is_device_disconnected(exc):
                raise backend_exceptions.BackendDisconnectedError(
                    "ITE 8258 device disconnected during initialization"
                ) from exc
            if device_exception_utils.is_device_busy(exc):
                raise backend_exceptions.BackendBusyError(
                    "ITE 8258 device is busy; another process may own it"
                ) from exc
            if isinstance(exc, RuntimeError):
                raise
            raise backend_exceptions.BackendIOError(f"ITE 8258 HID transport failed: {exc}") from exc

    def dimensions(self) -> tuple[int, int]:
        return (protocol.NUM_ROWS, protocol.NUM_COLS)

    def effects(self) -> dict[str, Any]:
        return {
            "rainbow": _effect_builder("screw_rainbow", extra=("direction",)),
            "rainbow_wave": _effect_builder("rainbow_wave", extra=("direction",)),
            "color_change": _effect_builder("color_change", extra=("color",)),
            "color_pulse": _effect_builder("color_pulse", extra=("color",)),
            "color_wave": _effect_builder("color_wave", extra=("direction", "color")),
            "smooth": _effect_builder("smooth", extra=("color",)),
        }

    def colors(self) -> dict[str, Any]:
        return {}
