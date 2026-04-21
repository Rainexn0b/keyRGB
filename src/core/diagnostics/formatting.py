from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from .model import DiagnosticsConfigSnapshot
from ._formatting_support import append_support_hints, append_sysfs_leds

if TYPE_CHECKING:
    from .model import Diagnostics


def _append_environment(lines: list[str], env: object) -> None:
    if not isinstance(env, Mapping) or not env:
        return

    lines.append("Environment:")
    for k in sorted(env.keys()):
        lines.append(f"  {k}={env[k]}")


def _append_system(lines: list[str], system: object) -> None:
    if not isinstance(system, Mapping) or not system:
        return

    lines.append("System:")
    for k in sorted(system.keys()):
        v = system[k]
        if isinstance(v, Mapping):
            lines.append(f"  {k}:")
            for kk in sorted(v.keys()):
                lines.append(f"    {kk}: {v[kk]}")
        else:
            lines.append(f"  {k}: {v}")


def _append_app(lines: list[str], app: object) -> None:
    if not isinstance(app, Mapping) or not app:
        return

    lines.append("App:")
    for k in sorted(app.keys()):
        lines.append(f"  {k}: {app[k]}")


def _append_power_supply(lines: list[str], power_supply: object) -> None:
    if not isinstance(power_supply, Mapping) or not power_supply:
        return

    lines.append("Power supply:")
    for name in sorted(power_supply.keys()):
        lines.append(f"  {name}:")
        entry = power_supply[name]
        if isinstance(entry, Mapping):
            for k in sorted(entry.keys()):
                lines.append(f"    {k}: {entry[k]}")


def _append_backends(lines: list[str], backends: object) -> None:
    if not isinstance(backends, Mapping) or not backends:
        return

    lines.append("Backends:")
    sel = backends.get("selected")
    req = backends.get("requested")
    if req is not None:
        lines.append(f"  requested: {req}")
    lines.append(f"  selected: {sel}")
    probes = backends.get("probes")
    if isinstance(probes, Sequence) and not isinstance(probes, str):
        for p in probes:
            if not isinstance(p, Mapping):
                continue
            lines.append(
                "  - {name}: available={available} stability={stability} evidence={evidence} confidence={confidence} reason={reason}".format(
                    name=p.get("name"),
                    available=p.get("available"),
                    stability=p.get("stability"),
                    evidence=(p.get("experimental_evidence") or "-"),
                    confidence=p.get("confidence"),
                    reason=p.get("reason"),
                )
            )
            ids = p.get("identifiers")
            if isinstance(ids, Mapping) and ids:
                for k in sorted(ids.keys()):
                    lines.append(f"      {k}: {ids[k]}")

    guided_speed_probes = backends.get("guided_speed_probes")
    if isinstance(guided_speed_probes, Sequence) and not isinstance(guided_speed_probes, str) and guided_speed_probes:
        lines.append("  guided_speed_probes:")
        for probe in guided_speed_probes:
            if not isinstance(probe, Mapping):
                continue
            lines.append(
                "    - {backend}: effect={effect} ui_speeds={ui_speeds}".format(
                    backend=probe.get("backend"),
                    effect=probe.get("effect_name"),
                    ui_speeds=probe.get("requested_ui_speeds"),
                )
            )
            for sample in probe.get("samples") or []:
                if not isinstance(sample, Mapping):
                    continue
                lines.append(
                    "      sample: ui={ui_speed} payload={payload_speed} raw={raw_speed_hex}".format(
                        ui_speed=sample.get("ui_speed"),
                        payload_speed=sample.get("payload_speed"),
                        raw_speed_hex=sample.get("raw_speed_hex"),
                    )
                )
            expectation = str(probe.get("expectation") or "").strip()
            if expectation:
                lines.append(f"      expectation: {expectation}")


def _append_usb_devices(lines: list[str], usb_devices: object) -> None:
    if not isinstance(usb_devices, Sequence) or isinstance(usb_devices, str) or not usb_devices:
        return

    lines.append("USB devices (sysfs):")
    for dev in usb_devices:
        if not isinstance(dev, Mapping):
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
        if isinstance(acc, Mapping):
            lines.append(f"      devnode_access: read={acc.get('read')} write={acc.get('write')}")

        holders = dev.get("devnode_open_by")
        if isinstance(holders, Sequence) and not isinstance(holders, str) and holders:
            lines.append("      devnode_open_by:")
            for h in holders:
                if not isinstance(h, Mapping):
                    continue
                self_tag = " (self)" if h.get("is_self") else ""
                lines.append(
                    f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}{self_tag}".rstrip()
                )
                if h.get("cmdline"):
                    lines.append(f"          cmdline: {h.get('cmdline')}")

        others = dev.get("devnode_open_by_others")
        if isinstance(others, Sequence) and not isinstance(others, str) and others:
            lines.append("      devnode_open_by_others:")
            for h in others:
                if not isinstance(h, Mapping):
                    continue
                lines.append(f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}".rstrip())


def _append_process(lines: list[str], process: object) -> None:
    if not isinstance(process, Mapping) or not process:
        return

    lines.append("Process:")
    for k in sorted(process.keys()):
        lines.append(f"  {k}: {process[k]}")


def _append_config(lines: list[str], config: object) -> None:
    if isinstance(config, DiagnosticsConfigSnapshot):
        config_dict = config.to_dict()
    elif isinstance(config, Mapping):
        config_dict = dict(config)
    else:
        return
    if not config_dict:
        return

    lines.append("Config:")
    present = config_dict.get("present")
    lines.append(f"  present: {present}")
    if config_dict.get("mtime") is not None:
        lines.append(f"  mtime: {config_dict.get('mtime')}")
    if isinstance(config_dict.get("settings"), Mapping):
        lines.append("  settings:")
        for k in sorted(config_dict["settings"].keys()):
            lines.append(f"    {k}: {config_dict['settings'][k]}")
    if config_dict.get("per_key_colors_count") is not None:
        lines.append(f"  per_key_colors_count: {config_dict.get('per_key_colors_count')}")


def _append_virt(lines: list[str], virt: object) -> None:
    if not isinstance(virt, Mapping) or not virt:
        return

    lines.append("Virtualization:")
    for k in sorted(virt.keys()):
        lines.append(f"  {k}: {virt[k]}")


def _append_dmi(lines: list[str], dmi: object, backends: object) -> None:
    if not isinstance(dmi, Mapping) or not dmi:
        return

    lines.append("DMI:")

    selection = backends.get("selection") if isinstance(backends, Mapping) else None
    if isinstance(selection, Mapping):
        pol = selection.get("policy")
        if pol:
            lines.append(f"  policy: {pol}")
        if selection.get("blocked"):
            lines.append(f"  selection_blocked: {selection.get('blocked_reason')}")
    for k in sorted(dmi.keys()):
        lines.append(f"  {k}: {dmi[k]}")


def _append_usb_ids(lines: list[str], usb_ids: object) -> None:
    if not isinstance(usb_ids, Sequence) or isinstance(usb_ids, str) or not usb_ids:
        return

    lines.append("USB IDs (best-effort):")
    for usb_id in usb_ids:
        lines.append(f"  - {usb_id}")


def _append_hints(lines: list[str], hints: object) -> None:
    if not isinstance(hints, Mapping) or not hints:
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
    append_support_hints(lines, diag.backends, diag.usb_devices, diag.usb_ids, diag.hints)
    _append_usb_devices(lines, diag.usb_devices)
    _append_process(lines, diag.process)
    _append_config(lines, diag.config)
    _append_virt(lines, diag.virt)
    _append_dmi(lines, diag.dmi, diag.backends)
    append_sysfs_leds(lines, diag.sysfs_leds, diag.leds, diag.backends)
    _append_usb_ids(lines, diag.usb_ids)
    _append_hints(lines, diag.hints)

    if not lines:
        return "(no diagnostics available)"

    return "\n".join(lines)
