from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_POWER_SUPPLY_ENUMERATION_EXCEPTIONS = (OSError,)
_POWER_SUPPLY_TEXT_READ_EXCEPTIONS = (OSError, UnicodeError)


def iter_ac_online_files(power_supply_root: Path) -> list[Path]:
    files: list[Path] = []
    try:
        for child in sorted(power_supply_root.iterdir()):
            if not child.is_dir():
                continue
            online = child / "online"
            if not online.exists():
                continue
            # Prefer devices that identify as Mains.
            typ = None
            try:
                typ = (child / "type").read_text(errors="ignore").strip().lower()
            except _POWER_SUPPLY_TEXT_READ_EXCEPTIONS:
                typ = None
            if typ == "mains":
                files.append(online)

        if files:
            return files
    except _POWER_SUPPLY_ENUMERATION_EXCEPTIONS:
        pass

    # Fallback: common names like AC/ACAD/AC0
    try:
        for online in sorted(power_supply_root.glob("AC*/online")):
            files.append(online)
    except _POWER_SUPPLY_ENUMERATION_EXCEPTIONS:
        pass

    return files


def read_on_ac_power(*, power_supply_root: Optional[Path] = None) -> Optional[bool]:
    if power_supply_root is None:
        power_supply_root = Path(os.environ.get("KEYRGB_SYSFS_POWER_SUPPLY_ROOT", "/sys/class/power_supply"))

    candidates = iter_ac_online_files(power_supply_root)
    if not candidates:
        return None

    for online_path in candidates:
        try:
            raw = online_path.read_text(errors="ignore").strip()
            if raw in ("1", "0"):
                return raw == "1"
        except _POWER_SUPPLY_TEXT_READ_EXCEPTIONS:
            continue

    return None
