from __future__ import annotations

import os
from typing import Any

from .io import read_text, run_command
from .paths import sysfs_dmi_root, sysfs_leds_root


def dmi_snapshot() -> dict[str, str]:
    dmi_root = sysfs_dmi_root()
    dmi_keys = [
        "sys_vendor",
        "product_name",
        "product_version",
        "product_family",
        "board_vendor",
        "board_name",
        "board_version",
        "bios_vendor",
        "bios_version",
        "bios_date",
    ]
    dmi: dict[str, str] = {}
    for key in dmi_keys:
        val = read_text(dmi_root / key)
        if val:
            dmi[key] = val
    return dmi


def sysfs_leds_snapshot() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (all_leds, keyboard_leds), best-effort."""

    leds_root = sysfs_leds_root()
    all_leds: list[dict[str, str]] = []
    leds: list[dict[str, str]] = []
    try:
        if leds_root.exists():
            for child in sorted(leds_root.iterdir(), key=lambda p: p.name):
                if not child.is_dir():
                    continue
                name = child.name
                entry: dict[str, str] = {"name": name, "path": str(child)}
                b = child / "brightness"
                m = child / "max_brightness"
                t = child / "trigger"
                if b.exists():
                    val = read_text(b)
                    if val is not None:
                        entry["brightness"] = val
                if m.exists():
                    val = read_text(m)
                    if val is not None:
                        entry["max_brightness"] = val
                if t.exists():
                    val = read_text(t)
                    if val is not None:
                        entry["trigger"] = val

                all_leds.append(entry)

                lower = name.lower()
                if "kbd" in lower or "keyboard" in lower:
                    leds.append(entry)
    except Exception:
        # Best-effort.
        all_leds = all_leds
        leds = leds

    return all_leds, leds


def usb_ids_snapshot(*, include_usb: bool) -> list[str]:
    if not include_usb:
        return []

    if os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1":
        # Under pytest, USB scans can have unintended side effects on some
        # keyboard controllers (e.g., backlight resets). Avoid importing pyusb
        # unless the user explicitly opted in.
        return []

    usb_ids: list[str] = []
    try:
        import usb.core  # type: ignore

        for dev in usb.core.find(find_all=True) or []:  # pragma: no cover
            try:
                vid = int(getattr(dev, "idVendor", 0))
                pid = int(getattr(dev, "idProduct", 0))
                usb_ids.append(f"{vid:04x}:{pid:04x}")
            except Exception:
                continue
        usb_ids = sorted(set(usb_ids))
    except Exception:
        usb_ids = []

    return usb_ids


def env_snapshot() -> dict[str, str]:
    env_keys = [
        "KEYRGB_BACKEND",
        "KEYRGB_USE_INSTALLED_ITE",
        "KEYRGB_DEBUG",
        "XDG_CURRENT_DESKTOP",
        "DESKTOP_SESSION",
    ]
    env: dict[str, str] = {}
    for k in env_keys:
        v = os.environ.get(k)
        if v:
            env[k] = v
    return env


def virt_snapshot() -> dict[str, str]:
    virt: dict[str, str] = {}
    virt_val = run_command(["systemd-detect-virt"])
    if virt_val:
        virt["systemd_detect_virt"] = virt_val
    return virt


def process_snapshot() -> dict[str, Any]:
    process: dict[str, Any] = {}
    try:
        process["pid"] = int(os.getpid())
        process["euid"] = int(os.geteuid())
        process["egid"] = int(os.getegid())
        # Keep group IDs numeric to avoid leaking usernames.
        try:
            process["groups"] = [int(g) for g in os.getgroups()]
        except Exception:
            pass
    except Exception:
        process = {}

    return process
