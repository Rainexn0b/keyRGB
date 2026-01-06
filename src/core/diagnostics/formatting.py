from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Diagnostics


def _append_environment(lines: list[str], env: object) -> None:
    if not isinstance(env, dict) or not env:
        return

    lines.append("Environment:")
    for k in sorted(env.keys()):
        lines.append(f"  {k}={env[k]}")


def _append_system(lines: list[str], system: object) -> None:
    if not isinstance(system, dict) or not system:
        return

    lines.append("System:")
    for k in sorted(system.keys()):
        v = system[k]
        if isinstance(v, dict):
            lines.append(f"  {k}:")
            for kk in sorted(v.keys()):
                lines.append(f"    {kk}: {v[kk]}")
        else:
            lines.append(f"  {k}: {v}")


def _append_app(lines: list[str], app: object) -> None:
    if not isinstance(app, dict) or not app:
        return

    lines.append("App:")
    for k in sorted(app.keys()):
        lines.append(f"  {k}: {app[k]}")


def _append_power_supply(lines: list[str], power_supply: object) -> None:
    if not isinstance(power_supply, dict) or not power_supply:
        return

    lines.append("Power supply:")
    for name in sorted(power_supply.keys()):
        lines.append(f"  {name}:")
        entry = power_supply[name]
        if isinstance(entry, dict):
            for k in sorted(entry.keys()):
                lines.append(f"    {k}: {entry[k]}")


def _append_backends(lines: list[str], backends: object) -> None:
    if not isinstance(backends, dict) or not backends:
        return

    lines.append("Backends:")
    sel = backends.get("selected")
    req = backends.get("requested")
    if req is not None:
        lines.append(f"  requested: {req}")
    lines.append(f"  selected: {sel}")
    probes = backends.get("probes")
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


def _append_usb_devices(lines: list[str], usb_devices: object) -> None:
    if not isinstance(usb_devices, list) or not usb_devices:
        return

    lines.append("USB devices (sysfs):")
    for dev in usb_devices:
        if not isinstance(dev, dict):
            continue
        lines.append(
            "  - {idVendor}:{idProduct} {product}".format(
                idVendor=dev.get("idVendor"),
                idProduct=dev.get("idProduct"),
                product=dev.get("product", ""),
            ).rstrip()
        )
        for k in (
            "manufacturer",
            "serial",
            "busnum",
            "devnum",
            "devnode",
            "driver",
        ):
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
                self_tag = " (self)" if h.get("is_self") else ""
                lines.append(
                    f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}{self_tag}".rstrip()
                )
                if h.get("cmdline"):
                    lines.append(f"          cmdline: {h.get('cmdline')}")

        others = dev.get("devnode_open_by_others")
        if isinstance(others, list) and others:
            lines.append("      devnode_open_by_others:")
            for h in others:
                if not isinstance(h, dict):
                    continue
                lines.append(f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}".rstrip())


def _append_process(lines: list[str], process: object) -> None:
    if not isinstance(process, dict) or not process:
        return

    lines.append("Process:")
    for k in sorted(process.keys()):
        lines.append(f"  {k}: {process[k]}")


def _append_config(lines: list[str], config: object) -> None:
    if not isinstance(config, dict) or not config:
        return

    lines.append("Config:")
    present = config.get("present")
    lines.append(f"  present: {present}")
    if config.get("mtime") is not None:
        lines.append(f"  mtime: {config.get('mtime')}")
    if isinstance(config.get("settings"), dict):
        lines.append("  settings:")
        for k in sorted(config["settings"].keys()):
            lines.append(f"    {k}: {config['settings'][k]}")
    if config.get("per_key_colors_count") is not None:
        lines.append(f"  per_key_colors_count: {config.get('per_key_colors_count')}")


def _append_virt(lines: list[str], virt: object) -> None:
    if not isinstance(virt, dict) or not virt:
        return

    lines.append("Virtualization:")
    for k in sorted(virt.keys()):
        lines.append(f"  {k}: {virt[k]}")


def _append_dmi(lines: list[str], dmi: object, backends: object) -> None:
    if not isinstance(dmi, dict) or not dmi:
        return

    lines.append("DMI:")

    selection = backends.get("selection") if isinstance(backends, dict) else None
    if isinstance(selection, dict):
        pol = selection.get("policy")
        if pol:
            lines.append(f"  policy: {pol}")
        if selection.get("blocked"):
            lines.append(f"  selection_blocked: {selection.get('blocked_reason')}")
    for k in sorted(dmi.keys()):
        lines.append(f"  {k}: {dmi[k]}")


def _append_sysfs_leds(
    lines: list[str],
    sysfs_leds: object,
    leds: object,
    backends: object,
) -> None:
    if isinstance(sysfs_leds, list) and sysfs_leds:
        lines.append("Sysfs LEDs:")
        for entry in sysfs_leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")
            if entry.get("brightness"):
                lines.append(f"      brightness: {entry['brightness']}")
            if entry.get("max_brightness"):
                lines.append(f"      max_brightness: {entry['max_brightness']}")
            if entry.get("trigger"):
                lines.append(f"      trigger: {entry['trigger']}")

                extra: list[str] = []
                if entry.get("tier") is not None:
                    extra.append(f"tier={entry.get('tier')}")
                if entry.get("provider") is not None:
                    extra.append(f"provider={entry.get('provider')}")
                if entry.get("priority") is not None:
                    extra.append(f"priority={entry.get('priority')}")
                if extra:
                    lines.append(f"      {' '.join(extra)}")

    if isinstance(leds, list) and leds and sysfs_leds != leds:
        lines.append("Keyboard LEDs (filtered):")
        for entry in leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")

        sysfs_cand = backends.get("sysfs_led_candidates") if isinstance(backends, dict) else None
        if isinstance(sysfs_cand, dict) and sysfs_cand:
            lines.append("  sysfs_led_candidates:")
            for k in ("root", "exists", "candidates_count"):
                if k in sysfs_cand:
                    lines.append(f"    {k}: {sysfs_cand.get(k)}")
            top = sysfs_cand.get("top")
            if isinstance(top, list) and top:
                lines.append("    top:")
                for e in top[:5]:
                    if not isinstance(e, dict):
                        continue
                    lines.append(f"      - {e.get('name')} score={e.get('score')}")


def _append_usb_ids(lines: list[str], usb_ids: object) -> None:
    if not isinstance(usb_ids, list) or not usb_ids:
        return

    lines.append("USB IDs (best-effort):")
    for usb_id in usb_ids:
        lines.append(f"  - {usb_id}")


def _append_hints(lines: list[str], hints: object) -> None:
    if not isinstance(hints, dict) or not hints:
        return

    lines.append("Hints:")
    if hints.get("platform_devices"):
        lines.append("  platform_devices:")
        for name in hints["platform_devices"]:
            lines.append(f"    - {name}")
    if hints.get("modules"):
        lines.append("  modules:")
        for name in hints["modules"]:
            lines.append(f"    - {name}")


def format_diagnostics_text(diag: "Diagnostics") -> str:
    """Format diagnostics for logs or copy/paste."""

    lines: list[str] = []

    _append_environment(lines, diag.env)
    _append_system(lines, diag.system)
    _append_app(lines, diag.app)
    _append_power_supply(lines, diag.power_supply)
    _append_backends(lines, diag.backends)
    _append_usb_devices(lines, diag.usb_devices)
    _append_process(lines, diag.process)
    _append_config(lines, diag.config)
    _append_virt(lines, diag.virt)
    _append_dmi(lines, diag.dmi, diag.backends)
    _append_sysfs_leds(lines, diag.sysfs_leds, diag.leds, diag.backends)
    _append_usb_ids(lines, diag.usb_ids)
    _append_hints(lines, diag.hints)

    if not lines:
        return "(no diagnostics available)"

    return "\n".join(lines)
