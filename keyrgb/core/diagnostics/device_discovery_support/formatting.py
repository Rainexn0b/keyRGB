from __future__ import annotations

from typing import Any


def format_device_discovery_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("Device discovery:")
    lines.append(f"  selected_backend: {payload.get('selected_backend')}")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        lines.append(f"  candidate_count: {summary.get('candidate_count')}")
        lines.append(f"  supported_count: {summary.get('supported_count')}")
        lines.append(f"  attention_count: {summary.get('attention_count')}")

    support_actions = payload.get("support_actions")
    if isinstance(support_actions, dict):
        lines.append(f"  suggested_issue_template: {support_actions.get('recommended_issue_template')}")
        lines.append(f"  suggested_issue_url: {support_actions.get('recommended_issue_url')}")
        next_steps = support_actions.get("next_steps")
        if isinstance(next_steps, list) and next_steps:
            lines.append("Recommended next steps:")
            for step in next_steps:
                lines.append(f"  - {step}")
        capture_commands = support_actions.get("optional_capture_commands")
        if isinstance(capture_commands, list) and capture_commands:
            lines.append("Optional deeper-evidence commands:")
            for command in capture_commands:
                lines.append(f"  - {command}")

    usb_ids = payload.get("usb_ids")
    if isinstance(usb_ids, list) and usb_ids:
        lines.append("USB IDs:")
        for usb_id in usb_ids:
            lines.append(f"  - {usb_id}")

    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        lines.append("Candidates:")
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            product = str(entry.get("product") or "").strip()
            label = f" {product}" if product else ""
            usb_vid = str(entry.get("usb_vid") or "").strip()
            usb_pid = str(entry.get("usb_pid") or "").strip()
            sysfs_led = str(entry.get("sysfs_led") or "").strip()
            sysfs_led_dir = str(entry.get("sysfs_led_dir") or "").strip()
            candidate_prefix = f"{usb_vid}:{usb_pid}" if usb_vid and usb_pid else "sysfs"
            lines.append(f"  - {candidate_prefix}{label} type={entry.get('device_type')} status={entry.get('status')}")
            action = entry.get("recommended_action")
            if action:
                lines.append(f"      next: {action}")
            probes = entry.get("probe_names")
            if isinstance(probes, list) and probes:
                lines.append(f"      probes: {', '.join(str(name) for name in probes if name)}")
            if sysfs_led:
                lines.append(f"      sysfs_led: {sysfs_led}")
            if sysfs_led_dir:
                lines.append(f"      sysfs_led_dir: {sysfs_led_dir}")
            hidraw_nodes = entry.get("hidraw_nodes")
            if isinstance(hidraw_nodes, list) and hidraw_nodes:
                lines.append(f"      hidraw: {', '.join(str(path) for path in hidraw_nodes if path)}")
            descriptor_sizes = entry.get("hidraw_descriptor_sizes")
            if isinstance(descriptor_sizes, list) and descriptor_sizes:
                lines.append(f"      hidraw_descriptor_sizes: {', '.join(str(size) for size in descriptor_sizes)}")
            elif isinstance(hidraw_nodes, list) and hidraw_nodes:
                lines.append("      hidraw_descriptor_sizes: unavailable (check permissions and rerun if needed)")

    secondary = payload.get("secondary_devices")
    if isinstance(secondary, dict):
        lines.append("Secondary devices:")
        lines.append(f"  experimental_backends_enabled: {secondary.get('experimental_backends_enabled')}")
        lines.append(f"  selected_device_context: {secondary.get('selected_device_context')}")
        software_target = secondary.get("software_effect_target")
        if isinstance(software_target, dict):
            lines.append(
                "  software_effect_target: "
                f"{software_target.get('current')} "
                f"(all_compatible_devices_enabled={software_target.get('all_compatible_devices_enabled')})"
            )
        virtual_routes = secondary.get("virtual_routes")
        if isinstance(virtual_routes, list) and virtual_routes:
            lines.append("  virtual zone routes:")
            for route in virtual_routes:
                if not isinstance(route, dict):
                    continue
                available = route.get("parent_available")
                reason = str(route.get("parent_reason") or "").strip()
                suffix = f" ({reason})" if reason and not available else ""
                lines.append(
                    f"    - {route.get('display_name')} [{route.get('backend_name')}] "
                    f"parent={route.get('parent_backend')} available={available}{suffix}"
                )
        aux_candidates = secondary.get("auxiliary_candidates")
        if isinstance(aux_candidates, list) and aux_candidates:
            lines.append("  auxiliary candidates:")
            for candidate in aux_candidates:
                if not isinstance(candidate, dict):
                    continue
                vid = str(candidate.get("usb_vid") or "").strip()
                pid = str(candidate.get("usb_pid") or "").strip()
                usb_id = f" {vid}:{pid}" if vid and pid else ""
                product = str(candidate.get("product") or "").strip()
                label = f" {product}" if product else ""
                lines.append(
                    f"    -{usb_id}{label} type={candidate.get('device_type')} "
                    f"status={candidate.get('status')} controls_available={candidate.get('controls_available')}"
                )
        expected = secondary.get("expected_tray_contexts")
        if isinstance(expected, list) and expected:
            lines.append("  expected tray device-context rows:")
            for context in expected:
                if not isinstance(context, dict):
                    continue
                lines.append(
                    f"    - {context.get('key')} type={context.get('device_type')} "
                    f"source={context.get('source')} controls_available={context.get('controls_available')}"
                )

    if not lines:
        return "(no discovery data available)"
    return "\n".join(lines)
