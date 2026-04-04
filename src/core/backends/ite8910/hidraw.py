from __future__ import annotations

import fcntl
import logging
import os
from dataclasses import dataclass
from pathlib import Path

HIDRAW_PATH_ENV = "KEYRGB_ITE8910_HIDRAW_PATH"

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_WRITE = 1
_IOC_READ = 2

logger = logging.getLogger(__name__)


def _ioc(dir_bits: int, type_bits: int, nr: int, size: int) -> int:
    return (
        ((dir_bits) << _IOC_DIRSHIFT)
        | ((type_bits) << _IOC_TYPESHIFT)
        | ((nr) << _IOC_NRSHIFT)
        | ((size) << _IOC_SIZESHIFT)
    )


def hidiocsfeature(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, ord("H"), 0x06, int(length))


@dataclass(frozen=True)
class HidrawDeviceInfo:
    hidraw_name: str
    devnode: Path
    sysfs_dir: Path
    vendor_id: int
    product_id: int
    hid_id: str
    hid_name: str = ""


def _parse_hid_id(value: str) -> tuple[int, int] | None:
    parts = str(value or "").strip().split(":")
    if len(parts) != 3:
        return None
    try:
        vendor_id = int(parts[1], 16)
        product_id = int(parts[2], 16)
    except ValueError:
        return None
    return vendor_id, product_id


def _parse_uevent_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def find_matching_hidraw_device(
    vendor_id: int,
    product_id: int,
    *,
    root: Path | None = None,
    dev_root: Path | None = None,
) -> HidrawDeviceInfo | None:
    forced_path = os.environ.get(HIDRAW_PATH_ENV)
    if forced_path:
        devnode = Path(forced_path)
        if devnode.exists():
            return HidrawDeviceInfo(
                hidraw_name=devnode.name,
                devnode=devnode,
                sysfs_dir=Path(),
                vendor_id=int(vendor_id),
                product_id=int(product_id),
                hid_id=f"forced:{int(vendor_id):04x}:{int(product_id):04x}",
            )

    root_dir = Path(root) if root is not None else Path("/sys/class/hidraw")
    if not root_dir.exists():
        return None

    device_root = Path(dev_root) if dev_root is not None else Path("/dev")

    for sysfs_dir in sorted(root_dir.glob("hidraw*"), key=lambda p: p.name.lower()):
        uevent_path = sysfs_dir / "device" / "uevent"
        if not uevent_path.exists():
            continue
        data = _parse_uevent_file(uevent_path)
        parsed = _parse_hid_id(data.get("HID_ID", ""))
        if parsed is None:
            continue
        found_vendor_id, found_product_id = parsed
        if found_vendor_id != int(vendor_id) or found_product_id != int(product_id):
            continue

        return HidrawDeviceInfo(
            hidraw_name=sysfs_dir.name,
            devnode=device_root / sysfs_dir.name,
            sysfs_dir=sysfs_dir,
            vendor_id=found_vendor_id,
            product_id=found_product_id,
            hid_id=data.get("HID_ID", ""),
            hid_name=data.get("HID_NAME", ""),
        )

    return None


class HidrawFeatureTransport:
    def __init__(self, devnode: Path) -> None:
        flags = os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= int(getattr(os, "O_CLOEXEC"))
        self.devnode = Path(devnode)
        self._fd: int | None = os.open(os.fspath(self.devnode), flags)

    def close(self) -> None:
        fd = getattr(self, "_fd", None)
        if fd is None:
            return
        try:
            os.close(int(fd))
        finally:
            self._fd = None

    def send_feature_report(self, report: bytes) -> int:
        payload = bytearray(report)
        if len(payload) <= 0:
            raise ValueError("feature report must not be empty")

        fd = self._fd
        if fd is None:
            raise RuntimeError("hidraw transport is closed")

        fcntl.ioctl(int(fd), hidiocsfeature(len(payload)), payload, True)
        return len(payload)

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, TypeError, ValueError):
            logger.debug("Ignoring hidraw transport cleanup failure", exc_info=True)


def open_matching_hidraw_transport(
    vendor_id: int,
    product_id: int,
    *,
    root: Path | None = None,
    dev_root: Path | None = None,
) -> tuple[HidrawFeatureTransport, HidrawDeviceInfo]:
    info = find_matching_hidraw_device(vendor_id, product_id, root=root, dev_root=dev_root)
    if info is None:
        raise FileNotFoundError(f"No hidraw device found for 0x{int(vendor_id):04x}:0x{int(product_id):04x}")
    return HidrawFeatureTransport(info.devnode), info
