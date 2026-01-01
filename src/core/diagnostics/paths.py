from __future__ import annotations

import os
from pathlib import Path


def sysfs_dmi_root() -> Path:
    # Test hook: allow overriding sysfs dmi root.
    return Path(os.environ.get("KEYRGB_SYSFS_DMI_ROOT", "/sys/class/dmi/id"))


def sysfs_leds_root() -> Path:
    # Keep aligned with sysfs-leds backend.
    return Path(os.environ.get("KEYRGB_SYSFS_LEDS_ROOT", "/sys/class/leds"))


def sysfs_usb_devices_root() -> Path:
    # Test hook: allow overriding sysfs USB device listing root.
    return Path(os.environ.get("KEYRGB_SYSFS_USB_ROOT", "/sys/bus/usb/devices"))


def usb_devnode_root() -> Path:
    # Test hook: allow overriding /dev/bus/usb root.
    return Path(os.environ.get("KEYRGB_USB_DEVNODE_ROOT", "/dev/bus/usb"))


def config_file_path() -> Path:
    # Test hook: allow overriding config path.
    p = os.environ.get("KEYRGB_CONFIG_PATH")
    if p:
        return Path(p)
    return Path.home() / ".config" / "keyrgb" / "config.json"
