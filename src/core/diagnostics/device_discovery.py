from __future__ import annotations

from typing import Any

from .collectors.backends import backend_probe_snapshot
from .device_discovery_support.formatting import format_device_discovery_text as _format_device_discovery_text
from .device_discovery_support.payload import build_device_discovery_payload
from .hidraw import hidraw_devices_snapshot
from .snapshots import usb_ids_snapshot
from .usb import usb_devices_snapshot


def collect_device_discovery(*, include_usb: bool = True) -> dict[str, Any]:
    backends = backend_probe_snapshot()
    usb_ids = usb_ids_snapshot(include_usb=include_usb)
    hidraw_devices = hidraw_devices_snapshot()
    return build_device_discovery_payload(
        backends=backends,
        usb_ids=list(usb_ids),
        hidraw_devices=hidraw_devices,
        usb_devices_loader=usb_devices_snapshot,
    )


def format_device_discovery_text(payload: dict[str, Any]) -> str:
    return _format_device_discovery_text(payload)
