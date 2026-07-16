from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.core.backends import exceptions as backend_exceptions
from src.core.backends.shared_hidraw_transport import (
    HidrawTransportProxy,
    SharedHidrawTransportManager,
)
from src.core.utils import exceptions as device_exception_utils

from .. import base
from ..policy import experimental_backends_enabled
from ..shared_hidraw_probe import (
    find_matching_ite8291_style_hidraw_device,
    identifiers_for_hidraw_match,
    open_matching_ite8291_style_hidraw_transport,
)
from . import protocol

if TYPE_CHECKING:
    from ..ite8291_perkey import hidraw
    from .profile_coordinator import Ite8258ChassisProfileCoordinator


_transport_manager: SharedHidrawTransportManager | None = None
_profile_coordinator: Ite8258ChassisProfileCoordinator | None = None


def _get_transport_manager() -> SharedHidrawTransportManager:
    global _profile_coordinator, _transport_manager
    if _transport_manager is None:
        from .profile_coordinator import Ite8258ChassisProfileCoordinator

        _transport_manager = SharedHidrawTransportManager()
        _profile_coordinator = Ite8258ChassisProfileCoordinator()
    return _transport_manager


def _get_profile_coordinator() -> Ite8258ChassisProfileCoordinator:
    global _profile_coordinator
    _get_transport_manager()
    if _profile_coordinator is None:
        from .profile_coordinator import Ite8258ChassisProfileCoordinator

        _profile_coordinator = Ite8258ChassisProfileCoordinator()
    return _profile_coordinator


def _find_matching_supported_hidraw_device() -> hidraw.HidrawDeviceInfo | None:
    return find_matching_ite8291_style_hidraw_device(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
    )


def _identifiers_for_match(match: hidraw.HidrawDeviceInfo) -> dict[str, str]:
    return identifiers_for_hidraw_match(match)


def _open_matching_transport() -> tuple[hidraw.HidrawFeatureOutputTransport, hidraw.HidrawDeviceInfo]:
    return open_matching_ite8291_style_hidraw_transport(
        product_ids=protocol.SUPPORTED_PRODUCT_IDS,
        forced_path_env=protocol.HIDRAW_PATH_ENV,
        backend_name="ite8258_perkey_chassis",
        vendor_id=protocol.VENDOR_ID,
        missing_label="ITE 8258 chassis",
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
class Ite8258ChassisBackend(base.KeyboardBackend):
    """Experimental keyboard-first Lenovo Gen10 composite ITE 8258 backend."""

    name: str = "ite8258_perkey_chassis"
    priority: int = 97
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
                reason="ite8258_perkey_chassis hardware scan disabled by KEYRGB_DISABLE_USB_SCAN",
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
        return base.BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=False)

    def _require_experimental(self) -> None:
        if not experimental_backends_enabled():
            raise RuntimeError(
                "ITE 8258 chassis support is classified as experimental. Enable Experimental backends in Settings "
                "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
            )

    def _acquire_transport_proxy(self) -> HidrawTransportProxy:
        self._require_experimental()
        try:
            return _get_transport_manager().acquire(
                self.name,
                opener=lambda: _open_matching_transport()[0],
            )
        except backend_exceptions.BACKEND_OPEN_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: HID transport open is a hardware driver boundary; recoverable driver exceptions are translated to BackendError subclasses here
            if device_exception_utils.is_permission_denied(exc):
                raise backend_exceptions.BackendPermissionError(
                    "Permission denied opening the ITE 8258 chassis hidraw device. Install the KeyRGB udev rules, "
                    "then reload udev or reboot/log out and back in."
                ) from exc
            if device_exception_utils.is_device_disconnected(exc):
                raise backend_exceptions.BackendDisconnectedError(
                    "ITE 8258 chassis device disconnected during initialization"
                ) from exc
            if device_exception_utils.is_device_busy(exc):
                raise backend_exceptions.BackendBusyError(
                    "ITE 8258 chassis device is busy; another process may own it"
                ) from exc
            if isinstance(exc, RuntimeError):
                raise
            raise backend_exceptions.BackendIOError(f"ITE 8258 chassis HID transport failed: {exc}") from exc

    def get_device(self) -> base.KeyboardDevice:
        proxy = self._acquire_transport_proxy()
        from .device import Ite8258ChassisKeyboardDevice

        return Ite8258ChassisKeyboardDevice(
            proxy.send_feature_report,
            transport=proxy,
            profile_coordinator=_get_profile_coordinator(),
        )

    def get_zone_device(self, zone_key: str) -> object:
        proxy = self._acquire_transport_proxy()
        from .device import Ite8258ChassisZoneDevice

        if zone_key == "logo":
            led_ids = protocol.LOGO_LED_IDS
        elif zone_key == "neon":
            led_ids = protocol.NEON_LED_IDS
        elif zone_key == "vent":
            led_ids = protocol.VENT_LED_IDS
        else:
            proxy.close()
            raise ValueError(f"Unknown ITE 8258 chassis zone: {zone_key}")

        return Ite8258ChassisZoneDevice(
            proxy.send_feature_report,
            zone_name=zone_key,
            led_ids=led_ids,
            transport=proxy,
            profile_coordinator=_get_profile_coordinator(),
        )

    def dimensions(self) -> tuple[int, int]:
        return (protocol.NUM_ROWS, protocol.NUM_COLS)

    def diagnostics(self) -> dict[str, Any]:
        matrix_cells = int(protocol.NUM_ROWS * protocol.NUM_COLS)
        mapped_leds = sum(1 for item in protocol.KEYBOARD_MATRIX_MAP if item is not None)
        return {
            "keyboard_matrix": {
                "rows": int(protocol.NUM_ROWS),
                "cols": int(protocol.NUM_COLS),
                "matrix_cells": matrix_cells,
                "mapped_leds": mapped_leds,
                "keyboard_led_ids": len(protocol.KEYBOARD_LED_IDS),
                "sparse": mapped_leds < matrix_cells,
                "sparse_holes": matrix_cells - mapped_leds,
                "row_mapped_counts": [
                    sum(
                        1
                        for col in range(protocol.NUM_COLS)
                        if protocol.KEYBOARD_MATRIX_MAP[(row * protocol.NUM_COLS) + col] is not None
                    )
                    for row in range(protocol.NUM_ROWS)
                ],
            }
        }

    def effects(self) -> dict[str, Any]:
        return {
            "rainbow": _effect_builder("screw_rainbow", extra=("direction",)),
            "rainbow_wave": _effect_builder("rainbow_wave", extra=("direction",)),
            "color_change": _effect_builder("color_change", extra=("color",)),
            "color_pulse": _effect_builder("color_pulse", extra=("color",)),
            "color_wave": _effect_builder("color_wave", extra=("direction", "color")),
            "smooth": _effect_builder("smooth", extra=("color",)),
            "rain": _effect_builder("rain", extra=("color",)),
            "ripple": _effect_builder("ripple", extra=("color",)),
            "audio_bounce": _effect_builder("audio_bounce"),
            "audio_ripple": _effect_builder("audio_ripple"),
            "type": _effect_builder("type", extra=("color",)),
        }

    def colors(self) -> dict[str, Any]:
        return {}


# Backend naming clarification:
# "ite8258_perkey_chassis" currently means "Lenovo Legion Pro 7 Gen10 (0x048d:0xc197)".
# The ITE 8258 chip may appear in other laptops with different PIDs and different
# zone configurations.  If a new PID is discovered, do not assume these LED IDs
# and zone layouts apply.  A future refactor should introduce a ChassisVariant
# registry that maps PID -> zone config, and virtual routes should be generated
# dynamically from the probe result instead of hardcoded in secondary_device_routes.py.
