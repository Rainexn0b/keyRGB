from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..base import BackendCapabilities, KeyboardDevice, KeyboardBackend, ProbeResult
from . import common
from . import privileged
from .device import SysfsLedKeyboardDevice

logger = logging.getLogger(__name__)


@dataclass
class SysfsLedsBackend(KeyboardBackend):
    name: str = "sysfs-leds"
    priority: int = 150

    def _find_leds(self) -> list[Path]:
        root = common._leds_root()
        if not root.exists():
            return []

        candidates: list[Path] = []
        try:
            for child in root.iterdir():
                if child.is_dir() and common._is_candidate_led(child.name):
                    candidates.append(child)
        except Exception:
            return []

        viable: list[tuple[int, str, Path]] = []
        for led_dir in candidates:
            b = led_dir / "brightness"
            m = led_dir / "max_brightness"
            if b.exists() and m.exists():
                viable.append((common._score_led_dir(led_dir), led_dir.name, led_dir))

        if not viable:
            return []

        # Highest score first; name is a deterministic tie-breaker.
        viable.sort(key=lambda t: (-t[0], t[1].lower()))
        
        # Filter out low-scoring candidates (e.g. noise like "micmute" that slipped through)
        # 0 is the baseline for "neutral", negatives are explicit "bad matches".
        return [t[2] for t in viable if t[0] >= 0]

    def probe(self) -> ProbeResult:
        found = self._find_leds()
        if not found:
            return ProbeResult(available=False, reason="no matching sysfs LED", confidence=0)

        # Primary is the highest scoring one
        led_dir = found[0]
        brightness_path = led_dir / "brightness"
        max_brightness_path = led_dir / "max_brightness"
        
        if not os.access(brightness_path, os.R_OK):
            return ProbeResult(
                available=False,
                reason="brightness not readable",
                confidence=0,
                identifiers={
                    "brightness": str(brightness_path),
                    "led": led_dir.name,
                    "led_dir": str(led_dir),
                },
            )

        if not os.access(brightness_path, os.W_OK):
            # Many kernel LED class nodes are root-writable only. If the optional
            # pkexec helper is present and supports LED writes, we can still
            # drive the backlight safely without running the whole app as root.
            if privileged.helper_supports_led_apply():
                return ProbeResult(
                    available=True,
                    reason="sysfs LED present (brightness root-only; using helper)",
                    confidence=70,
                    identifiers={
                        "brightness": str(brightness_path),
                        "led": led_dir.name,
                        "led_dir": str(led_dir),
                        "helper": privileged.power_helper_path(),
                    },
                )

            return ProbeResult(
                available=False,
                reason="brightness not writable (needs root or keyrgb-power-helper)",
                confidence=0,
                identifiers={
                    "brightness": str(brightness_path),
                    "led": led_dir.name,
                    "led_dir": str(led_dir),
                },
            )

        return ProbeResult(
            available=True,
            reason="sysfs LED present",
            confidence=85,
            identifiers={
                "brightness": str(brightness_path),
                "max_brightness": str(max_brightness_path),
                "led": led_dir.name,
                "led_dir": str(led_dir),
                "supports_multi_intensity": str((led_dir / "multi_intensity").exists()).lower(),
                "supports_color_attr": str((led_dir / "color").exists()).lower(),
                "all_zones": str([p.name for p in found]),
            },
        )

    def is_available(self) -> bool:
        return self.probe().available

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        found = self._find_leds()
        if not found:
            raise FileNotFoundError("No sysfs LED keyboard backlight found")
        
        return SysfsLedKeyboardDevice(
            primary_led_dir=found[0],
            all_led_dirs=found,
        )

    def dimensions(self) -> tuple[int, int]:
        # Not per-key. Return a common matrix size for legacy callers that assume
        # dimensions exist, but treat per_key=False as authoritative.
        return (6, 21)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
