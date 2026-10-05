"""Copy the hardware-access scripts and system payloads into an AppDir.

The AppImage must carry the same files the hardware-only installer writes.
It must not carry the AppImage downloader or the rest of the installer.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HARDWARE_ACCESS_APPDIR_RELATIVE = "usr/lib/keyrgb/hardware-access"

# Source path relative to the repo root, destination relative to the bundle root.
HARDWARE_ACCESS_FILES: tuple[tuple[str, str], ...] = (
    ("scripts/install_hardware_access.sh", "install_hardware_access.sh"),
    ("scripts/lib/hardware_access.sh", "lib/hardware_access.sh"),
    ("scripts/lib/uninstall_match.sh", "lib/uninstall_match.sh"),
    ("system/udev/99-ite8291-wootbook.rules", "system/udev/99-ite8291-wootbook.rules"),
    ("system/udev/99-keyrgb-sysfs-leds.rules", "system/udev/99-keyrgb-sysfs-leds.rules"),
    ("system/udev/99-keyrgb-input-uaccess.rules", "system/udev/99-keyrgb-input-uaccess.rules"),
    ("system/bin/keyrgb-power-helper", "system/bin/keyrgb-power-helper"),
    ("system/polkit/90-keyrgb-power-helper.rules", "system/polkit/90-keyrgb-power-helper.rules"),
    ("system/polkit/org.keyrgb.power-helper.policy", "system/polkit/org.keyrgb.power-helper.policy"),
)


def bundle_hardware_access(*, appdir: Path, root: Path) -> Path:
    """Copy the required hardware-access payload into ``appdir``.

    Raises ``SystemExit`` if a required file is missing or is a symlink.
    A partial bundle is not a successful AppImage.
    """

    dest_root = appdir / HARDWARE_ACCESS_APPDIR_RELATIVE
    for src_rel, dest_rel in HARDWARE_ACCESS_FILES:
        src = root / src_rel
        if src.is_symlink() or not src.is_file():
            raise SystemExit(f"Cannot bundle hardware-access payload: {src}")
        dest = dest_root / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return dest_root
