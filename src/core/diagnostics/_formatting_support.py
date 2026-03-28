from __future__ import annotations

from .io import parse_hex_int


def append_support_hints(
    lines: list[str],
    backends: object,
    usb_devices: object,
    usb_ids: object = None,
    hints: object = None,
) -> None:
    if not isinstance(backends, dict) or not backends:
        return

    probes = backends.get("probes")
    if not isinstance(probes, list) or not probes:
        return

    support_lines: list[str] = []

    usb_label_by_id: dict[tuple[str, str], str] = {}
    if isinstance(usb_devices, list):
        for dev in usb_devices:
            if not isinstance(dev, dict):
                continue
            vid = dev.get("idVendor")
            pid = dev.get("idProduct")
            if not isinstance(vid, str) or not isinstance(pid, str):
                continue
            product = dev.get("product")
            label = str(product) if product else ""
            usb_label_by_id[(vid.lower(), pid.lower())] = label

    unsupported_usb: list[dict[str, str]] = []
    for probe in probes:
        if not isinstance(probe, dict) or bool(probe.get("available")):
            continue

        ids = probe.get("identifiers")
        if not isinstance(ids, dict):
            continue

        vid_txt = ids.get("usb_vid")
        pid_txt = ids.get("usb_pid")
        if not isinstance(vid_txt, str) or not isinstance(pid_txt, str):
            continue

        reason = str(probe.get("reason") or "")
        reason_l = reason.lower()
        if "usb device present" not in reason_l or "unsupported" not in reason_l:
            continue

        entry: dict[str, str] = {
            "backend": str(probe.get("name") or ""),
            "vid": vid_txt,
            "pid": pid_txt,
            "reason": reason,
        }
        product_label = usb_label_by_id.get((vid_txt.lower(), pid_txt.lower()))
        if product_label:
            entry["product"] = product_label
        unsupported_usb.append(entry)

    if unsupported_usb:
        support_lines.append(
            "  One or more USB devices were detected but marked as unsupported (fail-closed) to avoid talking the wrong protocol."
        )

        for entry in unsupported_usb[:6]:
            product = entry.get("product", "")
            suffix = f" {product}" if product else ""
            support_lines.append(
                "  - {vid}:{pid}{suffix} (backend={backend})".format(
                    vid=entry.get("vid"),
                    pid=entry.get("pid"),
                    suffix=suffix,
                    backend=entry.get("backend"),
                )
            )
            support_lines.append(f"      reason: {entry.get('reason')}")

            vid_i = parse_hex_int(str(entry.get("vid") or ""))
            pid_i = parse_hex_int(str(entry.get("pid") or ""))
            if vid_i == 0x048D and pid_i in {0xC965, 0xC966, 0xC967, 0xC936}:
                support_lines.append(
                    "      note: this VID/PID is commonly reported on Lenovo Legion / IdeaPad Gaming keyboard RGB controllers."
                )
                support_lines.append(
                    "      next: please open an issue and include this diagnostics output + your laptop model."
                )

    seen_candidate_usb_ids = _collect_candidate_usb_ids(usb_ids=usb_ids, usb_devices=usb_devices)
    sysfs_available, sysfs_reason = _read_sysfs_backend_probe(probes)
    selected = backends.get("selected")
    selected_name = str(selected).strip().lower() if selected is not None else ""

    module_names: set[str] = set()
    if isinstance(hints, dict):
        modules = hints.get("modules")
        if isinstance(modules, list):
            for name in modules:
                if isinstance(name, str) and name.strip():
                    module_names.add(name.strip().lower())

    ite829x_loaded = "ite_829x" in module_names
    tuxedo_keyboard_loaded = "tuxedo_keyboard" in module_names
    clevo_platform_loaded = any(name in module_names for name in {"clevo_wmi", "clevo_acpi"})
    tuxedo_or_clevo_platform_loaded = tuxedo_keyboard_loaded or clevo_platform_loaded

    if (
        seen_candidate_usb_ids
        and not sysfs_available
        and "no matching sysfs led" in sysfs_reason.lower()
        and selected_name in {"", "none"}
    ):
        support_lines.append(
            "  Detected USB ID(s) associated with the TUXEDO/Clevo ITE 829x kernel-driver path, but no keyboard backlight sysfs LED was found."
        )
        support_lines.append(f"  - seen IDs: {', '.join(seen_candidate_usb_ids)}")
        if tuxedo_keyboard_loaded and not ite829x_loaded:
            support_lines.append(
                "  - observation: tuxedo_keyboard is loaded, but ite_829x was not seen in the module list."
            )
        if ite829x_loaded:
            support_lines.append(
                "  - next: verify ite_829x bound successfully and exposed rgb:kbd_backlight* under /sys/class/leds."
            )
        else:
            support_lines.append(
                "  - next: install or update tuxedo-drivers (or another package that provides ite_829x), then confirm the ite_829x module loads."
            )
        support_lines.append(
            "  - expectation: once rgb:kbd_backlight* exists, KeyRGB should detect it via the sysfs-leds backend."
        )

    if (
        not seen_candidate_usb_ids
        and tuxedo_or_clevo_platform_loaded
        and not sysfs_available
        and "no matching sysfs led" in sysfs_reason.lower()
        and selected_name in {"", "none"}
    ):
        support_lines.append(
            "  Detected TUXEDO/Clevo platform modules, but no keyboard backlight sysfs LED was found."
        )
        if tuxedo_keyboard_loaded:
            support_lines.append(
                "  - observation: tuxedo_keyboard is loaded, so this looks closer to a kernel-driver binding/export problem than a normal sysfs permission issue."
            )
        else:
            support_lines.append(
                "  - observation: Clevo platform modules are loaded, but no kbd_backlight LED node was exported."
            )
        support_lines.append(
            "  - next: check whether /sys/class/leds exposes rgb:kbd_backlight*, clevo::kbd_backlight, or tuxedo::kbd_backlight after boot."
        )
        if ite829x_loaded:
            support_lines.append(
                "  - next: verify the ite_829x path actually created LED class nodes for the keyboard."
            )
        else:
            support_lines.append(
                "  - next: inspect dmesg and lsmod for tuxedo, clevo, and ite_829x to confirm the keyboard-lighting subdriver is present and bound."
            )

    if not support_lines:
        return

    lines.append("Support hints:")
    lines.extend(support_lines)


def append_sysfs_leds(
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

                trigger_extra: list[str] = []
                if entry.get("tier") is not None:
                    trigger_extra.append(f"tier={entry.get('tier')}")
                if entry.get("provider") is not None:
                    trigger_extra.append(f"provider={entry.get('provider')}")
                if entry.get("priority") is not None:
                    trigger_extra.append(f"priority={entry.get('priority')}")
                if trigger_extra:
                    lines.append(f"      {' '.join(trigger_extra)}")

    if isinstance(leds, list) and leds and sysfs_leds != leds:
        lines.append("Keyboard LEDs (filtered):")
        for entry in leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")

        sysfs_cand = backends.get("sysfs_led_candidates") if isinstance(backends, dict) else None
        if not isinstance(sysfs_cand, dict) or not sysfs_cand:
            return

        lines.append("  sysfs_led_candidates:")
        for key in ("root", "exists", "candidates_count"):
            if key in sysfs_cand:
                lines.append(f"    {key}: {sysfs_cand.get(key)}")

        power_helper = sysfs_cand.get("power_helper")
        if isinstance(power_helper, dict) and power_helper:
            path = power_helper.get("path")
            exists = power_helper.get("exists")
            supports = power_helper.get("supports_led_apply")
            extra = []
            if "executable" in power_helper:
                extra.append(f"executable={power_helper.get('executable')}")
            if power_helper.get("mode") is not None:
                extra.append(f"mode={power_helper.get('mode')}")
            if power_helper.get("uid") is not None and power_helper.get("gid") is not None:
                extra.append(f"uid={power_helper.get('uid')} gid={power_helper.get('gid')}")
            suffix = (" " + " ".join(extra)) if extra else ""
            lines.append(f"    power_helper: path={path} exists={exists} supports_led_apply={supports}{suffix}")

        for key in ("pkexec_in_path", "pkexec_path", "sudo_in_path", "sudo_path"):
            if key in sysfs_cand:
                lines.append(f"    {key}: {sysfs_cand.get(key)}")

        top = sysfs_cand.get("top")
        if isinstance(top, list) and top:
            lines.append("    top:")
            for entry in top[:5]:
                if not isinstance(entry, dict):
                    continue
                top_extra: list[str] = []
                if entry.get("brightness_writable") is not None:
                    top_extra.append(f"writable={entry.get('brightness_writable')}")
                if entry.get("brightness_mode") is not None:
                    top_extra.append(f"mode={entry.get('brightness_mode')}")
                if entry.get("brightness_uid") is not None and entry.get("brightness_gid") is not None:
                    top_extra.append(f"uid={entry.get('brightness_uid')} gid={entry.get('brightness_gid')}")
                if entry.get("brightness_acl") is not None:
                    top_extra.append(f"acl={entry.get('brightness_acl')}")
                if entry.get("device_driver") is not None:
                    top_extra.append(f"driver={entry.get('device_driver')}")
                if entry.get("device_module") is not None:
                    top_extra.append(f"module={entry.get('device_module')}")
                suffix = (" " + " ".join(top_extra)) if top_extra else ""
                lines.append(f"      - {entry.get('name')} score={entry.get('score')}{suffix}")


def _collect_candidate_usb_ids(*, usb_ids: object, usb_devices: object) -> list[str]:
    seen_candidate_usb_ids: list[str] = []

    if isinstance(usb_ids, list):
        for entry in usb_ids:
            if not isinstance(entry, str):
                continue
            norm = entry.strip().lower()
            if norm in {"048d:8910", "048d:8911"} and norm not in seen_candidate_usb_ids:
                seen_candidate_usb_ids.append(norm)

    if seen_candidate_usb_ids or not isinstance(usb_devices, list):
        return seen_candidate_usb_ids

    for dev in usb_devices:
        if not isinstance(dev, dict):
            continue
        vid_i = parse_hex_int(str(dev.get("idVendor") or ""))
        pid_i = parse_hex_int(str(dev.get("idProduct") or ""))
        if vid_i == 0x048D and pid_i in {0x8910, 0x8911}:
            norm = f"{vid_i:04x}:{pid_i:04x}"
            if norm not in seen_candidate_usb_ids:
                seen_candidate_usb_ids.append(norm)

    return seen_candidate_usb_ids


def _read_sysfs_backend_probe(probes: list[object]) -> tuple[bool, str]:
    sysfs_reason = ""
    sysfs_available = False
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        if str(probe.get("name") or "").strip().lower() != "sysfs-leds":
            continue
        sysfs_reason = str(probe.get("reason") or "")
        sysfs_available = bool(probe.get("available"))
        break
    return sysfs_available, sysfs_reason