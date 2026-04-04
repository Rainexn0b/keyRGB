"""Auto-detect physical keyboard layout from Linux sysfs input capabilities.

On Linux, ISO keyboards report ``KEY_102ND`` (evdev code 86) in their input
event capabilities.  We inspect ``/sys/class/input/*/capabilities/key`` for
each input device that also reports letter-key codes (to skip power/media
buttons, mice, etc.).

Detection is best-effort:
- ``"iso"``  — a non-generic keyboard device reports KEY_102ND.
- ``"ansi"`` — keyboard devices found but no strong ISO evidence exists.
- ``"auto"`` — detection inconclusive (no keyboard devices readable, or only
    generic AT keyboard nodes report KEY_102ND).
"""

from __future__ import annotations

import glob
import logging
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

# Number of bits per ``unsigned long`` on the running architecture.
# Linux prints sysfs capability bitmaps as space-separated ``%lx`` longs.
_BITS_PER_LONG: int = struct.calcsize("P") * 8

# Evdev key codes used for detection.
_KEY_A: int = 30
_KEY_102ND: int = 86  # ISO extra key next to left shift


def _device_name_for_cap_path(cap_path: str) -> str:
    base = Path(cap_path).parent.parent
    candidates = (base / "name", base / "device" / "name")
    for path in candidates:
        try:
            name = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if name:
            return name
    return ""


def _is_generic_at_keyboard(name: str) -> bool:
    lowered = str(name or "").strip().lower()
    return lowered in {"at translated set 2 keyboard", "at translated set 2 keyboard"}


def detect_physical_layout() -> str:
    """Return ``"ansi"``, ``"iso"``, or ``"auto"`` based on sysfs probing."""

    found_keyboard = False
    weak_iso = False

    for cap_path in sorted(glob.glob("/sys/class/input/*/capabilities/key")):
        try:
            raw = Path(cap_path).read_text(encoding="ascii", errors="replace").strip()
        except OSError:
            continue

        words = raw.split()
        if not words:
            continue

        bitmap = 0
        for w in words:
            bitmap = (bitmap << _BITS_PER_LONG) | int(w, 16)

        # Skip non-keyboard devices (must report at least KEY_A).
        if not (bitmap >> _KEY_A) & 1:
            continue

        found_keyboard = True
        device_name = _device_name_for_cap_path(cap_path)

        if (bitmap >> _KEY_102ND) & 1:
            if _is_generic_at_keyboard(device_name):
                weak_iso = True
                logger.debug(
                    "Ignoring weak ISO hint from generic AT keyboard node %s (%s)",
                    cap_path,
                    device_name or "unknown",
                )
                continue

            logger.debug("ISO keyboard detected via %s (%s)", cap_path, device_name or "unknown")
            return "iso"

    if found_keyboard:
        if weak_iso:
            logger.debug("Physical layout detection inconclusive (only generic AT node exposed KEY_102ND)")
            return "auto"

        logger.debug("ANSI keyboard detected (no KEY_102ND in any input device)")
        return "ansi"

    logger.debug("Physical layout detection inconclusive (no keyboard devices found)")
    return "auto"
