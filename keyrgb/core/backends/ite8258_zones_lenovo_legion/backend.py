from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import keyrgb.core.backends.base as base  # noqa: PLR0402 - exact leaf import; package root intentionally exports no facade
import keyrgb.core.backends.exceptions as backend_exceptions
from keyrgb.core.backends.effect_contract import hardware_effect_builder
from keyrgb.core.utils import exceptions as device_exception_utils

from ..policies.backend_selection import experimental_backends_enabled
from ..shared_hidraw_probe import (
    find_matching_ite8291_style_hidraw_device,
    identifiers_for_hidraw_match,
    open_matching_ite8291_style_hidraw_transport,
)
from . import protocol

if TYPE_CHECKING:
    from ..ite8291_perkey import hidraw


def _find_matching_supported_hidraw_device() -> hidraw.HidrawDeviceInfo | None:
    return find_matching_ite8291_style_hidraw_device(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _open_matching_transport() -> tuple[hidraw.HidrawFeatureOutputTransport, hidraw.HidrawDeviceInfo]:
    return open_matching_ite8291_style_hidraw_transport(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
        backend_name="ite8258_zones_lenovo_legion",
        vendor_id=protocol.VENDOR_ID,
        missing_label="ITE 8258",
    )


def _identifiers_for_match(match: hidraw.HidrawDeviceInfo) -> dict[str, str]:
    return identifiers_for_hidraw_match(match)


def _effect_builder(effect_name: str, *, extra: tuple[str, ...] = ()):
    args = {"speed": None, "brightness": None}
    for key in extra:
        args[key] = None

    def build(**kwargs: object) -> dict[str, object]:
        _ = args
        payload: dict[str, object] = {"name": effect_name}
        payload.update(kwargs)
        return payload

    return hardware_effect_builder(build, accepted_kwargs=args)


@dataclass
class Ite8258Backend(base.KeyboardBackend):
    """Experimental 24-zone ITE 8258 hidraw backend."""

    name: str = "ite8258_zones_lenovo_legion"
    priority: int = 98
    stability: base.BackendStability = base.BackendStability.EXPERIMENTAL
    experimental_evidence: base.ExperimentalEvidence = base.ExperimentalEvidence.REVERSE_ENGINEERED

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> base.ProbeResult:
        identifiers = {
            "usb_vid": f"0x{protocol.VENDOR_ID:04x}",
            "usb_pid": "/".join(f"0x{pid:04x}" for pid in protocol.SUPPORTED_PRODUCT_IDS),
            "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
            "usage": f"0x{protocol.USAGE:04x}",
            "feature_report_size": str(protocol.PACKET_SIZE),
        }

        if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
            return base.ProbeResult(
                available=False,
                reason="ite8258_zones_lenovo_legion hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
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
        identifiers.update(
            {
                "usage_page": f"0x{protocol.USAGE_PAGE:04x}",
                "usage": f"0x{protocol.USAGE:04x}",
                "feature_report_size": str(protocol.PACKET_SIZE),
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
            reason=f"hidraw device present ({match.devnode})",
            confidence=83,
            identifiers=identifiers,
        )

    def capabilities(self) -> base.BackendCapabilities:
        return base.BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=True, palette=False)

    def get_device(self) -> base.KeyboardDevice:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8258 support is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

        try:
            transport, _info = _open_matching_transport()
            from .device import Ite8258KeyboardDevice

            return Ite8258KeyboardDevice(transport.send_feature_report, transport=transport)
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
