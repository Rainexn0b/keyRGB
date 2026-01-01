from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .collectors import (
    app_snapshot as _app_snapshot,
    backend_probe_snapshot as _backend_probe_snapshot,
    config_snapshot as _config_snapshot,
    list_module_hints as _list_module_hints,
    list_platform_hints as _list_platform_hints,
    power_supply_snapshot as _power_supply_snapshot,
    system_snapshot as _system_snapshot,
)
from .formatting import format_diagnostics_text
from .io import parse_hex_int as _parse_hex_int
from .io import read_text as _read_text
from .io import run_command as _run_command
from .paths import sysfs_dmi_root as _sysfs_dmi_root
from .paths import sysfs_leds_root as _sysfs_leds_root
from .usb import usb_devices_snapshot as _usb_devices_snapshot

from .model import Diagnostics


def collect_diagnostics(*, include_usb: bool = False) -> Diagnostics:
    """Collect best-effort diagnostics for Tongfang-focused support.

    This is intentionally read-only and should not require root.
    """

    dmi_root = _sysfs_dmi_root()
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
        val = _read_text(dmi_root / key)
        if val:
            dmi[key] = val

    leds_root = _sysfs_leds_root()
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
                    val = _read_text(b)
                    if val is not None:
                        entry["brightness"] = val
                if m.exists():
                    val = _read_text(m)
                    if val is not None:
                        entry["max_brightness"] = val
                if t.exists():
                    val = _read_text(t)
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

    usb_ids: list[str] = []
    if include_usb:
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

    virt: dict[str, str] = {}
    virt_val = _run_command(["systemd-detect-virt"])
    if virt_val:
        virt["systemd_detect_virt"] = virt_val

    system: dict[str, Any] = _system_snapshot()

    hints: dict[str, Any] = {}
    platform_hints = _list_platform_hints()
    if platform_hints:
        hints["platform_devices"] = platform_hints
    module_hints = _list_module_hints()
    if module_hints:
        hints["modules"] = module_hints

    app: dict[str, Any] = _app_snapshot()

    power_supply = _power_supply_snapshot()
    backends = _backend_probe_snapshot()

    # If any backend reported a USB VID/PID, collect sysfs USB details + devnode permissions.
    usb_targets: list[tuple[int, int]] = []
    try:
        probes = backends.get("probes")
        if isinstance(probes, list):
            for p in probes:
                if not isinstance(p, dict):
                    continue
                ids = p.get("identifiers")
                if not isinstance(ids, dict):
                    continue
                vid_txt = ids.get("usb_vid")
                pid_txt = ids.get("usb_pid")
                if isinstance(vid_txt, str) and isinstance(pid_txt, str):
                    vid = _parse_hex_int(vid_txt)
                    pid = _parse_hex_int(pid_txt)
                    if vid is not None and pid is not None:
                        usb_targets.append((vid, pid))
    except Exception:
        usb_targets = []

    usb_devices = _usb_devices_snapshot(usb_targets)
    config_snapshot = _config_snapshot()

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

    return Diagnostics(
        dmi=dmi,
        leds=leds,
        sysfs_leds=all_leds,
        usb_ids=usb_ids,
        env=env,
        virt=virt,
        system=system,
        hints=hints,
        app=app,
        power_supply=power_supply,
        backends=backends,
        usb_devices=usb_devices,
        config=config_snapshot,
        process=process,
    )


def main() -> None:
    diag = collect_diagnostics(include_usb=True)
    print(json.dumps(diag.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
