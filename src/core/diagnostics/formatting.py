from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diagnostics import Diagnostics


def format_diagnostics_text(diag: "Diagnostics") -> str:
    """Format diagnostics for logs or copy/paste."""

    lines: list[str] = []

    if diag.env:
        lines.append("Environment:")
        for k in sorted(diag.env.keys()):
            lines.append(f"  {k}={diag.env[k]}")

    if diag.system:
        lines.append("System:")
        for k in sorted(diag.system.keys()):
            v = diag.system[k]
            if isinstance(v, dict):
                lines.append(f"  {k}:")
                for kk in sorted(v.keys()):
                    lines.append(f"    {kk}: {v[kk]}")
            else:
                lines.append(f"  {k}: {v}")

    if diag.app:
        lines.append("App:")
        for k in sorted(diag.app.keys()):
            lines.append(f"  {k}: {diag.app[k]}")

    if diag.power_supply:
        lines.append("Power supply:")
        for name in sorted(diag.power_supply.keys()):
            lines.append(f"  {name}:")
            entry = diag.power_supply[name]
            if isinstance(entry, dict):
                for k in sorted(entry.keys()):
                    lines.append(f"    {k}: {entry[k]}")

    if diag.backends:
        lines.append("Backends:")
        sel = diag.backends.get("selected")
        req = diag.backends.get("requested")
        if req is not None:
            lines.append(f"  requested: {req}")
        lines.append(f"  selected: {sel}")
        probes = diag.backends.get("probes")
        if isinstance(probes, list):
            for p in probes:
                if not isinstance(p, dict):
                    continue
                lines.append(
                    "  - {name}: available={available} confidence={confidence} reason={reason}".format(
                        name=p.get("name"),
                        available=p.get("available"),
                        confidence=p.get("confidence"),
                        reason=p.get("reason"),
                    )
                )
                ids = p.get("identifiers")
                if isinstance(ids, dict) and ids:
                    for k in sorted(ids.keys()):
                        lines.append(f"      {k}: {ids[k]}")

    if diag.usb_devices:
        lines.append("USB devices (sysfs):")
        for dev in diag.usb_devices:
            if not isinstance(dev, dict):
                continue
            lines.append(
                "  - {idVendor}:{idProduct} {product}".format(
                    idVendor=dev.get("idVendor"),
                    idProduct=dev.get("idProduct"),
                    product=dev.get("product", ""),
                ).rstrip()
            )
            for k in ("manufacturer", "serial", "busnum", "devnum", "devnode", "driver"):
                if dev.get(k) is not None:
                    lines.append(f"      {k}: {dev.get(k)}")

            acc = dev.get("devnode_access")
            if isinstance(acc, dict):
                lines.append(f"      devnode_access: read={acc.get('read')} write={acc.get('write')}")

            holders = dev.get("devnode_open_by")
            if isinstance(holders, list) and holders:
                lines.append("      devnode_open_by:")
                for h in holders:
                    if not isinstance(h, dict):
                        continue
                    extra = " (self)" if h.get("is_self") else ""
                    lines.append(
                        f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}{extra}".rstrip()
                    )
                    if h.get("cmdline"):
                        lines.append(f"          cmdline: {h.get('cmdline')}")

            others = dev.get("devnode_open_by_others")
            if isinstance(others, list) and others:
                lines.append("      devnode_open_by_others:")
                for h in others:
                    if not isinstance(h, dict):
                        continue
                    lines.append(
                        f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}".rstrip()
                    )

    if diag.process:
        lines.append("Process:")
        for k in sorted(diag.process.keys()):
            lines.append(f"  {k}: {diag.process[k]}")

    if diag.config:
        lines.append("Config:")
        present = diag.config.get("present")
        lines.append(f"  present: {present}")
        if diag.config.get("mtime") is not None:
            lines.append(f"  mtime: {diag.config.get('mtime')}")
        if isinstance(diag.config.get("settings"), dict):
            lines.append("  settings:")
            for k in sorted(diag.config["settings"].keys()):
                lines.append(f"    {k}: {diag.config['settings'][k]}")
        if diag.config.get("per_key_colors_count") is not None:
            lines.append(f"  per_key_colors_count: {diag.config.get('per_key_colors_count')}")

    if diag.virt:
        lines.append("Virtualization:")
        for k in sorted(diag.virt.keys()):
            lines.append(f"  {k}: {diag.virt[k]}")

    if diag.dmi:
        lines.append("DMI:")
        for k in sorted(diag.dmi.keys()):
            lines.append(f"  {k}: {diag.dmi[k]}")

    if diag.sysfs_leds:
        lines.append("Sysfs LEDs:")
        for entry in diag.sysfs_leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")
            if entry.get("brightness"):
                lines.append(f"      brightness: {entry['brightness']}")
            if entry.get("max_brightness"):
                lines.append(f"      max_brightness: {entry['max_brightness']}")
            if entry.get("trigger"):
                lines.append(f"      trigger: {entry['trigger']}")

    if diag.leds and diag.sysfs_leds != diag.leds:
        lines.append("Keyboard LEDs (filtered):")
        for entry in diag.leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")

    if diag.usb_ids:
        lines.append("USB IDs (best-effort):")
        for usb_id in diag.usb_ids:
            lines.append(f"  - {usb_id}")

    if diag.hints:
        lines.append("Hints:")
        if diag.hints.get("platform_devices"):
            lines.append("  platform_devices:")
            for name in diag.hints["platform_devices"]:
                lines.append(f"    - {name}")
        if diag.hints.get("modules"):
            lines.append("  modules:")
            for name in diag.hints["modules"]:
                lines.append(f"    - {name}")

    if not lines:
        return "(no diagnostics available)"

    return "\n".join(lines)
