from __future__ import annotations

import json
import os
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
from .usb import usb_devices_snapshot as _usb_devices_snapshot

from .snapshots import (
    dmi_snapshot as _dmi_snapshot,
    env_snapshot as _env_snapshot,
    process_snapshot as _process_snapshot,
    sysfs_leds_snapshot as _sysfs_leds_snapshot,
    usb_ids_snapshot as _usb_ids_snapshot,
    virt_snapshot as _virt_snapshot,
)

from .model import Diagnostics


def collect_diagnostics(*, include_usb: bool = False) -> Diagnostics:
    """Collect best-effort diagnostics for Tongfang-focused support.

    This is intentionally read-only and should not require root.
    """

    dmi = _dmi_snapshot()
    all_leds, leds = _sysfs_leds_snapshot()
    usb_ids = _usb_ids_snapshot(include_usb=include_usb)
    env = _env_snapshot()
    virt = _virt_snapshot()

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

    process: dict[str, Any] = _process_snapshot()

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
