from __future__ import annotations

import array
import fcntl
import os
from pathlib import Path
import struct
from typing import Any


HID_MAX_DESCRIPTOR_SIZE = 4096

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_READ = 2


def _ioc(dir_bits: int, type_bits: int, nr: int, size: int) -> int:
    return (
        ((dir_bits) << _IOC_DIRSHIFT)
        | ((type_bits) << _IOC_TYPESHIFT)
        | ((nr) << _IOC_NRSHIFT)
        | ((size) << _IOC_SIZESHIFT)
    )


def _ior(type_char: str, nr: int, size: int) -> int:
    return _ioc(_IOC_READ, ord(type_char), nr, size)


def hidiocgrdescsize() -> int:
    return _ior("H", 0x01, struct.calcsize("I"))


def hidiocgrdesc(length: int) -> int:
    return _ior("H", 0x02, struct.calcsize("I") + int(length))


def _parse_hid_id(value: str) -> tuple[int, int] | None:
    parts = str(value or "").strip().split(":")
    if len(parts) != 3:
        return None
    try:
        vendor_id = int(parts[1], 16)
        product_id = int(parts[2], 16)
    except Exception:
        return None
    return vendor_id, product_id


def _parse_uevent_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()

    return out


def read_hidraw_report_descriptor(devnode: Path) -> dict[str, Any] | None:
    if os.environ.get("KEYRGB_DISABLE_HIDRAW_DESCRIPTOR_SCAN") == "1":
        return None

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= int(getattr(os, "O_CLOEXEC"))

    fd: int | None = None
    try:
        fd = os.open(os.fspath(devnode), flags)

        size_buf = array.array("I", [0])
        fcntl.ioctl(fd, hidiocgrdescsize(), size_buf, True)
        reported_size = int(size_buf[0]) if size_buf else 0
        size = max(0, min(HID_MAX_DESCRIPTOR_SIZE, reported_size))
        if size <= 0:
            return {"report_descriptor_size": 0, "report_descriptor_hex": ""}

        payload = bytearray(struct.calcsize("I") + size)
        struct.pack_into("I", payload, 0, size)
        fcntl.ioctl(fd, hidiocgrdesc(size), payload, True)
        actual_size = int(struct.unpack_from("I", payload, 0)[0])
        actual_size = max(0, min(size, actual_size))
        descriptor = bytes(payload[struct.calcsize("I") : struct.calcsize("I") + actual_size])
        return {
            "report_descriptor_size": actual_size,
            "report_descriptor_hex": descriptor.hex(),
        }
    except Exception as exc:
        return {"report_descriptor_error": str(exc)}
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass


def hidraw_devices_snapshot(*, root: Path | None = None, dev_root: Path | None = None) -> list[dict[str, Any]]:
    root_dir = Path(root) if root is not None else Path("/sys/class/hidraw")
    device_root = Path(dev_root) if dev_root is not None else Path("/dev")
    out: list[dict[str, Any]] = []

    try:
        if not root_dir.exists():
            return []

        for sysfs_dir in sorted(root_dir.glob("hidraw*"), key=lambda p: p.name.lower()):
            uevent_path = sysfs_dir / "device" / "uevent"
            if not uevent_path.exists():
                continue

            data = _parse_uevent_file(uevent_path)
            entry: dict[str, Any] = {
                "hidraw_name": sysfs_dir.name,
                "devnode": str(device_root / sysfs_dir.name),
                "sysfs_dir": str(sysfs_dir),
            }

            hid_id = str(data.get("HID_ID") or "")
            hid_name = str(data.get("HID_NAME") or "")
            if hid_id:
                entry["hid_id"] = hid_id
            if hid_name:
                entry["hid_name"] = hid_name

            parsed = _parse_hid_id(hid_id)
            if parsed is not None:
                vendor_id, product_id = parsed
                entry["vendor_id"] = f"0x{vendor_id:04x}"
                entry["product_id"] = f"0x{product_id:04x}"

            devnode = device_root / sysfs_dir.name
            entry["access"] = {
                "read": os.access(devnode, os.R_OK),
                "write": os.access(devnode, os.W_OK),
            }
            if bool(entry["access"].get("read")):
                descriptor_info = read_hidraw_report_descriptor(devnode)
                if isinstance(descriptor_info, dict):
                    entry.update(descriptor_info)
            out.append(entry)
    except Exception:
        return out

    return out