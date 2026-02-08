from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from ...resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS
from ..base import KeyboardDevice

logger = logging.getLogger(__name__)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def _rgb_to_hex(color: tuple[int, int, int]) -> str:
    r, g, b = (int(color[0]), int(color[1]), int(color[2]))
    return f"{_clamp(r, 0, 255):02x}{_clamp(g, 0, 255):02x}{_clamp(b, 0, 255):02x}"


def _brightness_to_asusctl_level(brightness: int) -> str:
    # KeyRGB uses 0..50.
    b = _clamp(brightness, 0, 50)
    if b <= 0:
        return "off"
    if b <= 16:
        return "low"
    if b <= 33:
        return "med"
    return "high"


def _asusctl_level_to_brightness(text: str) -> int:
    t = (text or "").strip().lower()
    if t in {"off", "0"}:
        return 0
    if t in {"low", "1"}:
        return 16
    if t in {"med", "medium", "2"}:
        return 33
    if t in {"high", "3"}:
        return 50
    return 0


@dataclass
class AsusctlAuraKeyboardDevice(KeyboardDevice):
    asusctl_path: str = "asusctl"
    zones: list[str] = field(default_factory=list)

    # Internal state
    _key_to_zone_idx: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        # Pre-calculate key mapping if we have multiple zones.
        if len(self.zones) > 1:
            width = BASE_IMAGE_SIZE[0]
            n_zones = len(self.zones)
            chunk_size = width / n_zones

            for key in REFERENCE_DEVICE_KEYS:
                cx = key.rect[0] + (key.rect[2] / 2)
                z_idx = int(cx // chunk_size)
                z_idx = max(0, min(z_idx, n_zones - 1))
                self._key_to_zone_idx[key.key_id] = z_idx

    def _run(self, args: list[str], *, timeout_s: float = 2.0) -> subprocess.CompletedProcess[str]:
        cmd = [self.asusctl_path, *args]
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )

    def _run_ok(self, args: list[str], *, timeout_s: float = 2.0) -> None:
        proc = self._run(args, timeout_s=timeout_s)
        if proc.returncode != 0:
            out = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"asusctl command failed ({proc.returncode}): {' '.join(args)}: {out}")

    def turn_off(self) -> None:
        # Brightness off is the most portable "off" across ASUS models.
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self.get_brightness() <= 0

    def get_brightness(self) -> int:
        # Expected output: "Current keyboard led brightness: Med"
        proc = self._run(["leds", "get"], timeout_s=2.0)
        if proc.returncode != 0:
            return 0

        m = re.search(r"brightness:\s*([A-Za-z0-9_-]+)", proc.stdout or "", flags=re.IGNORECASE)
        if not m:
            return 0
        return _asusctl_level_to_brightness(m.group(1))

    def set_brightness(self, brightness: int) -> None:
        level = _brightness_to_asusctl_level(brightness)
        self._run_ok(["leds", "set", level], timeout_s=2.0)

    def set_color(self, color, *, brightness: int):
        # Ensure backlight is on first (some devices ignore aura updates when off)
        self.set_brightness(brightness)

        hex_color = _rgb_to_hex((int(color[0]), int(color[1]), int(color[2])))

        # If zones are configured, set all zones to the same color.
        if self.zones:
            for z in self.zones:
                self._run_ok(["aura", "effect", "static", "-c", hex_color, "--zone", str(z)], timeout_s=2.0)
            return

        self._run_ok(["aura", "effect", "static", "-c", hex_color], timeout_s=2.0)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        # Note: `asusctl` CLI is zone-based. We implement "virtual per-key" mapping
        # by averaging keys into zones when multiple zones are configured.

        if not color_map:
            return

        # Single zone: average everything to a uniform color.
        if len(self.zones) <= 1:
            r_sum = g_sum = b_sum = count = 0
            for r, g, b in color_map.values():
                r_sum += int(r)
                g_sum += int(g)
                b_sum += int(b)
                count += 1

            if count:
                self.set_color((r_sum // count, g_sum // count, b_sum // count), brightness=brightness)
            return

        # Multi-zone: bucket by zone index.
        zone_lists: list[list[tuple[int, int, int]]] = [[] for _ in self.zones]

        for key_id, color in color_map.items():
            z_idx = self._key_to_zone_idx.get(key_id)
            if z_idx is None:
                continue
            zone_lists[z_idx].append((int(color[0]), int(color[1]), int(color[2])))

        # Apply brightness once.
        self.set_brightness(brightness)

        for i, colors in enumerate(zone_lists):
            if not colors:
                continue

            ar = sum(c[0] for c in colors) // len(colors)
            ag = sum(c[1] for c in colors) // len(colors)
            ab = sum(c[2] for c in colors) // len(colors)

            z = self.zones[i]
            self._run_ok(["aura", "effect", "static", "-c", _rgb_to_hex((ar, ag, ab)), "--zone", str(z)], timeout_s=2.0)

    def set_effect(self, effect_data) -> None:
        # Not wired yet. No-op.
        return
