from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from importlib import metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _run_command(argv: list[str], *, timeout_s: float = 1.5) -> Optional[str]:
    """Run a small diagnostic command in a best-effort, read-only way."""

    if not argv:
        return None

    exe = argv[0]
    if not shutil.which(exe):
        return None

    try:
        proc = subprocess.run(
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        out = (proc.stdout or "").strip()
        return out if out else None
    except Exception:
        return None


def _sysfs_dmi_root() -> Path:
    # Test hook: allow overriding sysfs dmi root.
    return Path(os.environ.get("KEYRGB_SYSFS_DMI_ROOT", "/sys/class/dmi/id"))


def _sysfs_leds_root() -> Path:
    # Keep aligned with sysfs-leds backend.
    return Path(os.environ.get("KEYRGB_SYSFS_LEDS_ROOT", "/sys/class/leds"))


def _sysfs_usb_devices_root() -> Path:
    # Test hook: allow overriding sysfs USB device listing root.
    return Path(os.environ.get("KEYRGB_SYSFS_USB_ROOT", "/sys/bus/usb/devices"))


def _usb_devnode_root() -> Path:
    # Test hook: allow overriding /dev/bus/usb root.
    return Path(os.environ.get("KEYRGB_USB_DEVNODE_ROOT", "/dev/bus/usb"))


def _config_file_path() -> Path:
    # Test hook: allow overriding config path.
    p = os.environ.get("KEYRGB_CONFIG_PATH")
    if p:
        return Path(p)
    return Path.home() / ".config" / "keyrgb" / "config.json"


def _read_kv_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE files like /etc/os-release."""

    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"')
            data[k.strip()] = v
    except Exception:
        return {}
    return data


def _parse_hex_int(text: str) -> Optional[int]:
    try:
        s = text.strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        return int(s, 16)
    except Exception:
        return None


def _proc_open_holders(target_path: Path, *, limit: int = 10, pid_limit: int = 5000) -> list[dict[str, Any]]:
    """Best-effort scan of /proc/*/fd to find processes holding a file open.

    This is useful for diagnosing "device detected but can't control" issues
    caused by other software holding the USB device node.
    """

    proc_root = Path("/proc")
    holders: list[dict[str, Any]] = []

    try:
        target_str = str(target_path)
        target_real = str(target_path.resolve()) if target_path.exists() else target_str

        if not proc_root.exists():
            return []

        checked = 0
        for child in proc_root.iterdir():
            if len(holders) >= limit or checked >= pid_limit:
                break

            if not child.is_dir() or not child.name.isdigit():
                continue
            checked += 1

            pid = int(child.name)
            fd_dir = child / "fd"
            if not fd_dir.exists():
                continue

            matched = False
            try:
                for fd in fd_dir.iterdir():
                    try:
                        link = os.readlink(fd)
                    except Exception:
                        continue
                    if link == target_str or link == target_real:
                        matched = True
                        break
            except PermissionError:
                continue
            except Exception:
                continue

            if not matched:
                continue

            info: dict[str, Any] = {"pid": pid, "is_self": (pid == os.getpid())}
            comm = _read_text(child / "comm")
            if comm:
                info["comm"] = comm
            try:
                exe = child / "exe"
                if exe.exists():
                    info["exe"] = str(exe.resolve())
            except Exception:
                pass

            # Best-effort command line (may be empty for kernel threads).
            try:
                cmdline_path = child / "cmdline"
                if cmdline_path.exists():
                    raw = cmdline_path.read_bytes()
                    # NUL-separated argv.
                    parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\x00") if p]
                    if parts:
                        # Keep it short to avoid overly verbose diagnostics.
                        joined = " ".join(parts)
                        info["cmdline"] = joined[:300]
            except Exception:
                pass

            holders.append(info)

        return holders
    except Exception:
        return holders


def _usb_devices_snapshot(target_ids: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Collect best-effort USB device details from sysfs.

    This is intentionally non-invasive: no device open, no control transfers.
    """

    if not target_ids:
        return []

    targets = {(int(v), int(p)) for (v, p) in target_ids}
    root = _sysfs_usb_devices_root()
    out: list[dict[str, Any]] = []

    try:
        if not root.exists():
            return []

        for dev in sorted(root.iterdir(), key=lambda p: p.name):
            if not dev.is_dir():
                continue

            vid_txt = _read_text(dev / "idVendor")
            pid_txt = _read_text(dev / "idProduct")
            if not vid_txt or not pid_txt:
                continue

            vid = _parse_hex_int(vid_txt)
            pid = _parse_hex_int(pid_txt)
            if vid is None or pid is None or (vid, pid) not in targets:
                continue

            entry: dict[str, Any] = {
                "sysfs_path": str(dev),
                "idVendor": f"0x{vid:04x}",
                "idProduct": f"0x{pid:04x}",
            }

            for k in ("manufacturer", "product", "serial", "bcdDevice", "speed"):
                v = _read_text(dev / k)
                if v:
                    entry[k] = v

            busnum_txt = _read_text(dev / "busnum")
            devnum_txt = _read_text(dev / "devnum")
            if busnum_txt and devnum_txt:
                entry["busnum"] = busnum_txt
                entry["devnum"] = devnum_txt

                try:
                    bus_i = int(busnum_txt)
                    dev_i = int(devnum_txt)
                    devnode = _usb_devnode_root() / f"{bus_i:03d}" / f"{dev_i:03d}"
                    entry["devnode"] = str(devnode)
                    if devnode.exists():
                        st = devnode.stat()
                        entry["devnode_mode"] = oct(int(st.st_mode) & 0o777)
                        entry["devnode_uid"] = int(st.st_uid)
                        entry["devnode_gid"] = int(st.st_gid)
                        entry["devnode_access"] = {
                            "read": bool(os.access(devnode, os.R_OK)),
                            "write": bool(os.access(devnode, os.W_OK)),
                        }
                        holders = _proc_open_holders(devnode)
                        if holders:
                            entry["devnode_open_by"] = holders
                            others = [h for h in holders if isinstance(h, dict) and not bool(h.get("is_self"))]
                            if others:
                                entry["devnode_open_by_others"] = others
                    else:
                        entry["devnode_exists"] = False
                except Exception:
                    pass

            # Attempt to capture a bound driver name if available.
            try:
                drv = dev / "driver"
                if drv.exists() and drv.is_symlink():
                    entry["driver"] = drv.resolve().name
            except Exception:
                pass

            out.append(entry)

        return out
    except Exception:
        return out


def _config_snapshot() -> dict[str, Any]:
    """Collect a small snapshot of KeyRGB config (best-effort).

    Intentionally avoids dumping large maps (like per-key colors) and avoids
    embedding user-specific paths.
    """

    cfg_path = _config_file_path()
    out: dict[str, Any] = {"present": False}

    try:
        if not cfg_path.exists():
            return out
        out["present"] = True
        try:
            st = cfg_path.stat()
            out["mtime"] = int(st.st_mtime)
        except Exception:
            pass

        data = json.loads(cfg_path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(data, dict):
            return out

        whitelist = (
            "effect",
            "speed",
            "brightness",
            "color",
            "autostart",
            "os_autostart",
            "power_management_enabled",
            "power_off_on_suspend",
            "power_off_on_lid_close",
            "power_restore_on_resume",
            "power_restore_on_lid_open",
            "battery_saver_enabled",
            "battery_saver_brightness",
            "ac_lighting_enabled",
            "ac_lighting_brightness",
            "battery_lighting_enabled",
            "battery_lighting_brightness",
        )
        settings: dict[str, Any] = {}
        for k in whitelist:
            if k in data:
                settings[k] = data[k]
        if settings:
            out["settings"] = settings

        pk = data.get("per_key_colors")
        if isinstance(pk, dict):
            out["per_key_colors_count"] = len(pk)

        return out
    except Exception as exc:
        out["error"] = str(exc)
        return out


def _list_platform_hints() -> list[str]:
    """Return a small list of platform device names hinting at laptop vendors."""

    candidates: list[str] = []
    root = Path("/sys/bus/platform/devices")
    patterns = (
        "tuxedo",
        "tongfang",
        "clevo",
        "ite",
        "wmi",
        "asus",
        "dell",
        "thinkpad",
        "msi",
        "acer",
        "hp",
        "lenovo",
    )

    try:
        if not root.exists():
            return []
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            name = child.name.lower()
            if any(p in name for p in patterns):
                candidates.append(child.name)
        return candidates[:80]
    except Exception:
        return []


def _list_module_hints() -> list[str]:
    """Return a small list of loaded kernel modules relevant to keyboard backlight support."""

    modules_path = Path("/proc/modules")
    keep = re.compile(r"(tuxedo|clevo|tongfang|ite|i8042|atkbd|hid|hid_.*|wmi|acpi)", re.IGNORECASE)
    out: list[str] = []
    try:
        if not modules_path.exists():
            return []
        for line in modules_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            # Format: name size use_count deps state address
            name = (line.split() or [""])[0]
            if name and keep.search(name):
                out.append(name)
        # Preserve order, unique.
        seen: set[str] = set()
        uniq: list[str] = []
        for m in out:
            if m in seen:
                continue
            seen.add(m)
            uniq.append(m)
        return uniq[:120]
    except Exception:
        return []


def _power_supply_snapshot() -> dict[str, Any]:
    """Collect a tiny power-supply snapshot (read-only, best-effort)."""

    root = Path("/sys/class/power_supply")
    out: dict[str, Any] = {}
    try:
        if not root.exists():
            return {}

        for dev in sorted(root.iterdir(), key=lambda p: p.name):
            if not dev.is_dir():
                continue

            entry: dict[str, str] = {}
            for key in ("type", "status", "online", "capacity", "charge_now", "energy_now"):
                val = _read_text(dev / key)
                if val is not None and val != "":
                    entry[key] = val

            if entry:
                out[dev.name] = entry

        return out
    except Exception:
        return {}


def _backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort).

    This helps support answer "why didn't KeyRGB find my keyboard?" by including
    the probe reason/confidence for each backend.
    """

    try:
        from .backends.base import ProbeResult  # noqa: F401
        from .backends.registry import iter_backends, select_backend
    except Exception:
        return {}

    probes: list[dict[str, Any]] = []
    for backend in iter_backends():
        try:
            probe_fn = getattr(backend, "probe", None)
            if callable(probe_fn):
                result = probe_fn()
                available = bool(getattr(result, "available", False))
                reason = str(getattr(result, "reason", ""))
                confidence = int(getattr(result, "confidence", 0) or 0)
                identifiers = getattr(result, "identifiers", None)
            else:
                available = bool(backend.is_available())
                reason = "is_available"
                confidence = 50 if available else 0
                identifiers = None
        except Exception as exc:
            available = False
            reason = f"probe exception: {exc}"
            confidence = 0
            identifiers = None

        entry: dict[str, Any] = {
            "name": getattr(backend, "name", backend.__class__.__name__),
            "available": available,
            "confidence": confidence,
            "reason": reason,
        }
        if identifiers:
            entry["identifiers"] = dict(identifiers)
        probes.append(entry)

    selected = None
    try:
        selected_backend = select_backend()
        selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception:
        selected = None

    return {
        "selected": selected,
        "requested": (os.environ.get("KEYRGB_BACKEND") or "auto"),
        "probes": probes,
    }


@dataclass(frozen=True)
class Diagnostics:
    dmi: dict[str, str]
    leds: list[dict[str, str]]
    sysfs_leds: list[dict[str, str]]
    usb_ids: list[str]
    env: dict[str, str]
    virt: dict[str, str]
    system: dict[str, Any]
    hints: dict[str, Any]
    app: dict[str, Any]
    power_supply: dict[str, Any]
    backends: dict[str, Any]
    usb_devices: list[dict[str, Any]]
    config: dict[str, Any]
    process: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dmi": dict(self.dmi),
            "leds": list(self.leds),
            "sysfs_leds": list(self.sysfs_leds),
            "usb_ids": list(self.usb_ids),
            "env": dict(self.env),
            "virt": dict(self.virt),
            "system": dict(self.system),
            "hints": dict(self.hints),
            "app": dict(self.app),
            "power_supply": dict(self.power_supply),
            "backends": dict(self.backends),
            "usb_devices": list(self.usb_devices),
            "config": dict(self.config),
            "process": dict(self.process),
        }


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

    system: dict[str, Any] = {}
    try:
        u = platform.uname()
        system["kernel_release"] = u.release
        system["machine"] = u.machine
    except Exception:
        pass
    try:
        system["python"] = sys.version.split()[0]
    except Exception:
        pass

    os_release = _read_kv_file(Path("/etc/os-release"))
    if os_release:
        # Keep only common, stable keys.
        keep_keys = ("NAME", "PRETTY_NAME", "ID", "VERSION_ID", "VARIANT_ID")
        system["os_release"] = {k: os_release[k] for k in keep_keys if k in os_release}

    hints: dict[str, Any] = {}
    platform_hints = _list_platform_hints()
    if platform_hints:
        hints["platform_devices"] = platform_hints
    module_hints = _list_module_hints()
    if module_hints:
        hints["modules"] = module_hints

    app: dict[str, Any] = {}
    # Best-effort version reporting. Distribution name may vary, so try a couple.
    for dist_name in ("keyrgb", "Keyrgb", "KeyRGB"):
        try:
            app["version"] = metadata.version(dist_name)
            app["dist"] = dist_name
            break
        except Exception:
            continue

    # Optional helper library used on some hardware.
    for dist_name in ("ite8291r3-ctl", "ite8291r3_ctl"):
        try:
            app["ite8291r3_ctl_version"] = metadata.version(dist_name)
            break
        except Exception:
            continue

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


def format_diagnostics_text(diag: Diagnostics) -> str:
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
                    extra = ""
                    if h.get("is_self"):
                        extra = " (self)"
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
                    lines.append(f"        - pid={h.get('pid')} comm={h.get('comm', '')} exe={h.get('exe', '')}".rstrip())

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


def main() -> None:
    diag = collect_diagnostics(include_usb=True)
    print(json.dumps(diag.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
