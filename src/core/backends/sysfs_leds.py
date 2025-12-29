from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .base import BackendCapabilities, KeyboardDevice, KeyboardBackend, ProbeResult


def _leds_root() -> Path:
    # Test hook: allow overriding the sysfs root.
    return Path(os.environ.get("KEYRGB_SYSFS_LEDS_ROOT", "/sys/class/leds"))


def _is_candidate_led(name: str) -> bool:
    n = name.lower()
    return ("kbd" in n) or ("keyboard" in n)


def _read_int(path: Path) -> int:
    return int(path.read_text(encoding="utf-8").strip())


def _write_int(path: Path, value: int) -> None:
    path.write_text(f"{int(value)}\n", encoding="utf-8")


@dataclass
class SysfsLedKeyboardDevice(KeyboardDevice):
    brightness_path: Path
    max_brightness_path: Path

    def _max(self) -> int:
        try:
            m = _read_int(self.max_brightness_path)
            return max(1, int(m))
        except Exception:
            return 1

    def _read_sysfs_brightness(self) -> int:
        try:
            return max(0, int(_read_int(self.brightness_path)))
        except Exception:
            return 0

    def turn_off(self) -> None:
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self.get_brightness() <= 0

    def get_brightness(self) -> int:
        # Normalize sysfs brightness into KeyRGB's "hardware" 0..50 scale.
        sysfs_value = self._read_sysfs_brightness()
        max_value = self._max()
        return int(round((sysfs_value / max_value) * 50))

    def set_brightness(self, brightness: int) -> None:
        # Map KeyRGB's 0..50 brightness scale into sysfs range.
        b = max(0, min(50, int(brightness)))
        max_value = self._max()
        sysfs_value = int(round((b / 50) * max_value))
        _write_int(self.brightness_path, sysfs_value)

    def set_color(self, color, *, brightness: int):
        # Brightness-only backend: ignore color and apply brightness.
        self.set_brightness(brightness)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        # Not supported. No-op to avoid crashing if legacy code attempts per-key.
        self.set_brightness(brightness)

    def set_effect(self, effect_data) -> None:
        # Not supported. No-op.
        return


@dataclass
class SysfsLedsBackend(KeyboardBackend):
    name: str = "sysfs-leds"
    priority: int = 80

    def _find_led(self) -> Optional[tuple[Path, Path]]:
        root = _leds_root()
        if not root.exists():
            return None

        candidates: list[Path] = []
        try:
            for child in root.iterdir():
                if child.is_dir() and _is_candidate_led(child.name):
                    candidates.append(child)
        except Exception:
            return None

        # Prefer candidates that look like a keyboard backlight.
        candidates.sort(key=lambda p: ("kbd" not in p.name.lower(), p.name))

        for led_dir in candidates:
            b = led_dir / "brightness"
            m = led_dir / "max_brightness"
            if b.exists() and m.exists():
                return b, m

        return None

    def probe(self) -> ProbeResult:
        found = self._find_led()
        if found is None:
            return ProbeResult(available=False, reason="no matching sysfs LED", confidence=0)

        brightness_path, max_brightness_path = found
        if not os.access(brightness_path, os.R_OK):
            return ProbeResult(
                available=False,
                reason="brightness not readable",
                confidence=0,
                identifiers={"brightness": str(brightness_path)},
            )

        if not os.access(brightness_path, os.W_OK):
            return ProbeResult(
                available=False,
                reason="brightness not writable (udev permissions missing?)",
                confidence=0,
                identifiers={"brightness": str(brightness_path)},
            )

        return ProbeResult(
            available=True,
            reason="sysfs LED present",
            confidence=85,
            identifiers={
                "brightness": str(brightness_path),
                "max_brightness": str(max_brightness_path),
            },
        )

    def is_available(self) -> bool:
        return self.probe().available

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        found = self._find_led()
        if found is None:
            raise FileNotFoundError("No sysfs LED keyboard backlight found")
        brightness_path, max_brightness_path = found
        return SysfsLedKeyboardDevice(brightness_path=brightness_path, max_brightness_path=max_brightness_path)

    def dimensions(self) -> tuple[int, int]:
        # Not per-key. Return a common matrix size for legacy callers that assume
        # dimensions exist, but treat per_key=False as authoritative.
        return (6, 21)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
