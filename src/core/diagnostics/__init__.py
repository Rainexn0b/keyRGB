from __future__ import annotations

import argparse
import json
from typing import Any

from . import collectors as diagnostics_collectors
from . import formatting as diagnostics_formatting
from . import io as diagnostics_io
from . import model as diagnostics_model
from . import snapshots as diagnostics_snapshots
from . import usb as diagnostics_usb

_app_snapshot = diagnostics_collectors.app_snapshot
_backend_probe_snapshot = diagnostics_collectors.backend_probe_snapshot
_config_snapshot = diagnostics_collectors.config_snapshot
_list_module_hints = diagnostics_collectors.list_module_hints
_list_platform_hints = diagnostics_collectors.list_platform_hints
_power_supply_snapshot = diagnostics_collectors.power_supply_snapshot
_system_snapshot = diagnostics_collectors.system_snapshot
_system_power_mode_snapshot = diagnostics_collectors.system_power_mode_snapshot
format_diagnostics_text = diagnostics_formatting.format_diagnostics_text
_parse_hex_int = diagnostics_io.parse_hex_int
Diagnostics = diagnostics_model.Diagnostics
_dmi_snapshot = diagnostics_snapshots.dmi_snapshot
_env_snapshot = diagnostics_snapshots.env_snapshot
_process_snapshot = diagnostics_snapshots.process_snapshot
_sysfs_leds_snapshot = diagnostics_snapshots.sysfs_leds_snapshot
_usb_ids_snapshot = diagnostics_snapshots.usb_ids_snapshot
_virt_snapshot = diagnostics_snapshots.virt_snapshot
_usb_devices_snapshot = diagnostics_usb.usb_devices_snapshot

_POWER_MODE_SNAPSHOT_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)

__all__ = [
    "Diagnostics",
    "collect_diagnostics",
    "format_diagnostics_text",
]


def _usb_targets_from_backend_probes(backends: object) -> list[tuple[int, int]]:
    if not isinstance(backends, dict):
        return []

    probes = backends.get("probes")
    if not isinstance(probes, list):
        return []

    usb_targets: list[tuple[int, int]] = []
    for probe in probes:
        if not isinstance(probe, dict):
            continue

        identifiers = probe.get("identifiers")
        if not isinstance(identifiers, dict):
            continue

        vid_txt = identifiers.get("usb_vid")
        pid_txt = identifiers.get("usb_pid")
        if not isinstance(vid_txt, str) or not isinstance(pid_txt, str):
            continue

        vid = _parse_hex_int(vid_txt)
        pid = _parse_hex_int(pid_txt)
        if vid is None or pid is None:
            continue

        usb_targets.append((vid, pid))

    return usb_targets


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
    try:
        system["power_mode"] = _system_power_mode_snapshot()
    except _POWER_MODE_SNAPSHOT_ERRORS:
        pass

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
    usb_targets = _usb_targets_from_backend_probes(backends)

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
    parser = argparse.ArgumentParser(
        prog="keyrgb-diagnostics",
        description="Collect best-effort KeyRGB diagnostics (read-only).",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Print human-readable diagnostics instead of JSON.",
    )
    parser.add_argument(
        "--no-usb",
        action="store_true",
        help="Skip USB enumeration (avoids pyusb scans).",
    )
    args = parser.parse_args()

    diag = collect_diagnostics(include_usb=not bool(args.no_usb))
    if args.text:
        print(format_diagnostics_text(diag))
    else:
        print(json.dumps(diag.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
