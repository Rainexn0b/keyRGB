"""Shared hidraw probe/open helpers for ITE backends.

Protocol encoding stays backend-local. These helpers only cover repeated glue:
forced-path / product-id matching, identifier maps, and feature-output open.

Two scanner families exist in-tree:

- **ite8291-style** (`ite8291_perkey.hidraw`): multi-PID + backend-specific forced path.
- **ite8910-style** (`ite8910_perkey.hidraw`): single VID/PID lookup; backends own their
  forced-path env and multi-PID fan-out.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from .ite8291_perkey.hidraw import HidrawDeviceInfo, HidrawFeatureOutputTransport
    from .ite8910_perkey.hidraw import (
        HidrawDeviceInfo as Ite8910HidrawDeviceInfo,
        HidrawFeatureTransport as Ite8910HidrawFeatureTransport,
    )

_MatchT = TypeVar("_MatchT")


class _HidrawMatch(Protocol):
    @property
    def vendor_id(self) -> int: ...

    @property
    def product_id(self) -> int: ...

    @property
    def devnode(self) -> Path: ...

    @property
    def hid_name(self) -> str: ...


def usb_scan_disabled() -> bool:
    return os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1"


def identifiers_for_hidraw_match(
    match: _HidrawMatch,
    *,
    include_bcd_device: bool = False,
) -> dict[str, str]:
    identifiers = {
        "usb_vid": f"0x{int(match.vendor_id):04x}",
        "usb_pid": f"0x{int(match.product_id):04x}",
        "hidraw": str(match.devnode),
    }
    hid_name = getattr(match, "hid_name", "") or ""
    if hid_name:
        identifiers["hid_name"] = str(hid_name)
    if include_bcd_device:
        bcd = getattr(match, "bcd_device", None)
        if bcd is not None:
            identifiers["usb_bcd_device"] = f"0x{int(bcd):04x}"
    return identifiers


def find_matching_ite8291_style_hidraw_device(
    *,
    product_ids: tuple[int, ...],
    forced_path_env: str,
) -> HidrawDeviceInfo | None:
    """Match using the ite8291_perkey hidraw scanner (forced path + VID/PID)."""
    from .ite8291_perkey import hidraw

    return hidraw.find_matching_hidraw_device(
        product_ids=tuple(int(pid) for pid in product_ids),
        forced_path_env=forced_path_env,
    )


def open_matching_ite8291_style_hidraw_transport(
    *,
    product_ids: tuple[int, ...],
    forced_path_env: str,
    backend_name: str,
    vendor_id: int,
    missing_label: str,
) -> tuple[HidrawFeatureOutputTransport, HidrawDeviceInfo]:
    """Open a feature-output transport for an ite8291-style matched device."""
    from .ite8291_perkey import hidraw

    supported = tuple(int(pid) for pid in product_ids)
    info = find_matching_ite8291_style_hidraw_device(
        product_ids=supported,
        forced_path_env=forced_path_env,
    )
    if info is None:
        raise FileNotFoundError(
            f"No hidraw device found for supported {missing_label} IDs: "
            + ", ".join(f"0x{int(vendor_id):04x}:0x{pid:04x}" for pid in supported)
        )
    return hidraw.HidrawFeatureOutputTransport(info.devnode, backend_name=backend_name), info


def find_matching_ite8910_style_hidraw_device(
    *,
    vendor_id: int,
    product_ids: tuple[int, ...],
    forced_path_env: str,
    forced_product_id: int,
    find_matching_fn: Callable[[int, int], _MatchT | None],
    device_info_factory: Callable[..., _MatchT],
) -> _MatchT | None:
    """Match with a backend-owned forced path, then multi-PID ite8910-style scan.

    ``find_matching_fn`` and ``device_info_factory`` are injected so unit tests can
    monkeypatch the backend module's public scanner while still sharing glue.
    """
    forced_path = os.environ.get(forced_path_env)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return device_info_factory(
                hidraw_name=devnode.name,
                devnode=devnode,
                sysfs_dir=Path(),
                vendor_id=int(vendor_id),
                product_id=int(forced_product_id),
                hid_id=f"forced:{int(vendor_id):04x}:{int(forced_product_id):04x}",
            )

    for product_id in product_ids:
        match = find_matching_fn(int(vendor_id), int(product_id))
        if match is not None:
            return match
    return None


def open_matching_ite8910_style_hidraw_transport(
    *,
    vendor_id: int,
    product_ids: tuple[int, ...],
    forced_path_env: str,
    forced_product_id: int,
    backend_name: str,
    missing_label: str,
    find_matching_fn: Callable[[int, int], Ite8910HidrawDeviceInfo | None],
    device_info_factory: Callable[..., Ite8910HidrawDeviceInfo],
) -> tuple[Ite8910HidrawFeatureTransport, Ite8910HidrawDeviceInfo]:
    """Open a feature transport for an ite8910-style matched device."""
    from .ite8910_perkey import hidraw

    supported = tuple(int(pid) for pid in product_ids)
    info = find_matching_ite8910_style_hidraw_device(
        vendor_id=int(vendor_id),
        product_ids=supported,
        forced_path_env=forced_path_env,
        forced_product_id=int(forced_product_id),
        find_matching_fn=find_matching_fn,
        device_info_factory=device_info_factory,
    )
    if info is None:
        raise FileNotFoundError(
            f"No hidraw device found for supported {missing_label} IDs: "
            + ", ".join(f"0x{int(vendor_id):04x}:0x{pid:04x}" for pid in supported)
        )
    return hidraw.HidrawFeatureTransport(info.devnode, backend_name=backend_name), info
