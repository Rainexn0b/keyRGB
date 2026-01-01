from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .io import parse_hex_int, read_text
from .paths import sysfs_usb_devices_root, usb_devnode_root
from .proc import proc_open_holders


def usb_devices_snapshot(target_ids: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Collect best-effort USB device details from sysfs.

    This is intentionally non-invasive: no device open, no control transfers.
    """

    if not target_ids:
        return []

    targets = {(int(v), int(p)) for (v, p) in target_ids}
    root = sysfs_usb_devices_root()
    out: list[dict[str, Any]] = []

    try:
        if not root.exists():
            return []

        for dev in sorted(root.iterdir(), key=lambda p: p.name):
            if not dev.is_dir():
                continue

            vid_txt = read_text(dev / "idVendor")
            pid_txt = read_text(dev / "idProduct")
            if not vid_txt or not pid_txt:
                continue

            vid = parse_hex_int(vid_txt)
            pid = parse_hex_int(pid_txt)
            if vid is None or pid is None or (vid, pid) not in targets:
                continue

            entry: dict[str, Any] = {
                "sysfs_path": str(dev),
                "idVendor": f"0x{vid:04x}",
                "idProduct": f"0x{pid:04x}",
            }

            for k in ("manufacturer", "product", "serial", "bcdDevice", "speed"):
                v = read_text(dev / k)
                if v:
                    entry[k] = v

            busnum_txt = read_text(dev / "busnum")
            devnum_txt = read_text(dev / "devnum")
            if busnum_txt and devnum_txt:
                entry["busnum"] = busnum_txt
                entry["devnum"] = devnum_txt

                try:
                    bus_i = int(busnum_txt)
                    dev_i = int(devnum_txt)
                    devnode = usb_devnode_root() / f"{bus_i:03d}" / f"{dev_i:03d}"
                    entry["devnode"] = str(devnode)
                    if devnode.exists():
                        st = devnode.stat()
                        entry["devnode_mode"] = oct(int(st.st_mode) & 0o777)
                        entry["devnode_uid"] = int(st.st_uid)
                        entry["devnode_gid"] = int(st.st_gid)
                        entry["devnode_access"] = {
                            "read": bool(os.access(devnode, os.R_OK)),
                            "write": bool(os.access(devnode, os.W_OK)),
                        }
                        holders = proc_open_holders(devnode)
                        if holders:
                            entry["devnode_open_by"] = holders
                            others = [h for h in holders if isinstance(h, dict) and not bool(h.get("is_self"))]
                            if others:
                                entry["devnode_open_by_others"] = others
                    else:
                        entry["devnode_exists"] = False
                except Exception:
                    pass

            # Attempt to capture a bound driver name if available.
            try:
                drv = dev / "driver"
                if drv.exists() and drv.is_symlink():
                    entry["driver"] = drv.resolve().name
            except Exception:
                pass

            out.append(entry)

        return out
    except Exception:
        return out
