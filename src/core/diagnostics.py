from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _sysfs_dmi_root() -> Path:
    # Test hook: allow overriding sysfs dmi root.
    return Path(os.environ.get("KEYRGB_SYSFS_DMI_ROOT", "/sys/class/dmi/id"))


def _sysfs_leds_root() -> Path:
    # Keep aligned with sysfs-leds backend.
    return Path(os.environ.get("KEYRGB_SYSFS_LEDS_ROOT", "/sys/class/leds"))


@dataclass(frozen=True)
class Diagnostics:
    dmi: dict[str, str]
    leds: list[dict[str, str]]
    usb_ids: list[str]
    env: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dmi": dict(self.dmi),
            "leds": list(self.leds),
            "usb_ids": list(self.usb_ids),
            "env": dict(self.env),
        }


def collect_diagnostics(*, include_usb: bool = False) -> Diagnostics:
    """Collect best-effort diagnostics for Tongfang-focused support.

    This is intentionally read-only and should not require root.
    """

    dmi_root = _sysfs_dmi_root()
    dmi_keys = ["sys_vendor", "product_name", "board_name"]
    dmi: dict[str, str] = {}
    for key in dmi_keys:
        val = _read_text(dmi_root / key)
        if val:
            dmi[key] = val

    leds_root = _sysfs_leds_root()
    leds: list[dict[str, str]] = []
    try:
        if leds_root.exists():
            for child in sorted(leds_root.iterdir(), key=lambda p: p.name):
                if not child.is_dir():
                    continue
                name = child.name
                lower = name.lower()
                if "kbd" not in lower and "keyboard" not in lower:
                    continue
                entry = {"name": name, "path": str(child)}
                b = child / "brightness"
                m = child / "max_brightness"
                if b.exists():
                    entry["brightness"] = str(b)
                if m.exists():
                    entry["max_brightness"] = str(m)
                leds.append(entry)
    except Exception:
        # Best-effort.
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

    return Diagnostics(dmi=dmi, leds=leds, usb_ids=usb_ids, env=env)


def format_diagnostics_text(diag: Diagnostics) -> str:
    """Format diagnostics for logs or copy/paste."""

    lines: list[str] = []

    if diag.env:
        lines.append("Environment:")
        for k in sorted(diag.env.keys()):
            lines.append(f"  {k}={diag.env[k]}")

    if diag.dmi:
        lines.append("DMI:")
        for k in sorted(diag.dmi.keys()):
            lines.append(f"  {k}: {diag.dmi[k]}")

    if diag.leds:
        lines.append("Sysfs LEDs:")
        for entry in diag.leds:
            lines.append(f"  - {entry.get('name')} ({entry.get('path')})")
            if entry.get("brightness"):
                lines.append(f"      brightness: {entry['brightness']}")
            if entry.get("max_brightness"):
                lines.append(f"      max_brightness: {entry['max_brightness']}")

    if diag.usb_ids:
        lines.append("USB IDs (best-effort):")
        for usb_id in diag.usb_ids:
            lines.append(f"  - {usb_id}")

    if not lines:
        return "(no diagnostics available)"

    return "\n".join(lines)


def main() -> None:
    diag = collect_diagnostics(include_usb=True)
    print(json.dumps(diag.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
