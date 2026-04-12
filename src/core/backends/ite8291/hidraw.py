from __future__ import annotations

import fcntl
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from . import protocol

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
    bcd_device: int | None = None


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


def _read_hex_file(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return int(raw, 16)
    except ValueError:
        return None


def _find_usb_device_hex_attr(sysfs_dir: Path, attr_name: str) -> int | None:
    try:
        device_dir = (sysfs_dir / "device").resolve()
    except OSError:
        return None

    for candidate_dir in (device_dir, *device_dir.parents):
        value = _read_hex_file(candidate_dir / attr_name)
        if value is not None:
            return value
    return None


def _forced_info(devnode: Path, *, product_id: int) -> HidrawDeviceInfo | None:
    if not devnode.exists():
        return None
    return HidrawDeviceInfo(
        hidraw_name=devnode.name,
        devnode=devnode,
        sysfs_dir=Path(),
        vendor_id=protocol.VENDOR_ID,
        product_id=int(product_id),
        hid_id=f"forced:{protocol.VENDOR_ID:04x}:{int(product_id):04x}",
    )


def find_matching_hidraw_device(
    *,
    root: Path | None = None,
    dev_root: Path | None = None,
    product_ids: tuple[int, ...] | None = None,
    forced_path_env: str | None = None,
) -> HidrawDeviceInfo | None:
    supported_product_ids = tuple(int(pid) for pid in (product_ids or protocol.SUPPORTED_PRODUCT_IDS))
    forced_path = os.environ.get(forced_path_env or protocol.HIDRAW_PATH_ENV)
    if forced_path:
        info = _forced_info(Path(forced_path), product_id=supported_product_ids[0])
        if info is not None:
            return info

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
        vendor_id, product_id = parsed
        if vendor_id != protocol.VENDOR_ID or product_id not in supported_product_ids:
            continue

        return HidrawDeviceInfo(
            hidraw_name=sysfs_dir.name,
            devnode=device_root / sysfs_dir.name,
            sysfs_dir=sysfs_dir,
            vendor_id=vendor_id,
            product_id=product_id,
            hid_id=data.get("HID_ID", ""),
            hid_name=data.get("HID_NAME", ""),
            bcd_device=_find_usb_device_hex_attr(sysfs_dir, "bcdDevice"),
        )

    return None


def _os_cloexec_flag_or_zero() -> int:
    try:
        return int(os.O_CLOEXEC)
    except AttributeError:
        return 0


class HidrawFeatureOutputTransport:
    def __init__(self, devnode: Path) -> None:
        flags = int(os.O_RDWR) | _os_cloexec_flag_or_zero()
        self.devnode = Path(devnode)
        self._fd: int | None = os.open(os.fspath(self.devnode), flags)

    def close(self) -> None:
        fd = self._fd
        if fd is None:
            return
        try:
            os.close(int(fd))
        finally:
            self._fd = None

    def send_feature_report(self, report: bytes) -> int:
        payload = bytearray(report)
        if not payload:
            raise ValueError("feature report must not be empty")

        fd = self._fd
        if fd is None:
            raise RuntimeError("hidraw transport is closed")

        fcntl.ioctl(int(fd), hidiocsfeature(len(payload)), payload, True)
        return len(payload)

    def write_output_report(self, report: bytes) -> int:
        payload = bytes(report)
        if not payload:
            raise ValueError("output report must not be empty")

        fd = self._fd
        if fd is None:
            raise RuntimeError("hidraw transport is closed")

        return int(os.write(int(fd), payload))

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, TypeError, ValueError):
            logger.debug("Ignoring hidraw transport cleanup failure", exc_info=True)


def open_matching_hidraw_transport(
    *,
    product_ids: tuple[int, ...] | None = None,
    forced_path_env: str | None = None,
) -> tuple[HidrawFeatureOutputTransport, HidrawDeviceInfo]:
    supported_product_ids = tuple(int(pid) for pid in (product_ids or protocol.SUPPORTED_PRODUCT_IDS))
    info = find_matching_hidraw_device(product_ids=supported_product_ids, forced_path_env=forced_path_env)
    if info is None:
        raise FileNotFoundError(
            "No hidraw device found for supported ITE 8291 IDs: "
            + ", ".join(f"0x{protocol.VENDOR_ID:04x}:0x{pid:04x}" for pid in supported_product_ids)
        )
    return HidrawFeatureOutputTransport(info.devnode), info
