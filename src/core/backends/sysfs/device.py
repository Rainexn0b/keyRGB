from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from ...resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS
from ..base import BackendCapabilities, KeyboardDevice
from ._device_methods import set_zone_color_method as _set_zone_color_method
from ._device_methods import to_sysfs_brightness_method as _to_sysfs_brightness_method
from . import common
from . import privileged

logger = logging.getLogger(__name__)

_SYSFS_STATE_ERRORS = (OSError, ValueError)
_CHANNEL_GROUP_STATE_ERRORS = (OSError, RuntimeError, ValueError)
_CAPABILITY_PROBE_ERRORS = (OSError, RuntimeError)


@dataclass
class SysfsLedKeyboardDevice(KeyboardDevice):
    primary_led_dir: Path
    all_led_dirs: list[Path] = field(default_factory=list)

    # Internal state
    _zones: list[dict] = field(default_factory=list, init=False, repr=False)
    _key_to_zone_idx: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _channel_group_color: tuple[int, int, int] | None = field(default=None, init=False, repr=False)
    _channel_group_brightness: int | None = field(default=None, init=False, repr=False)

    def _detect_ite8297_channel_group(self) -> dict[str, Path] | None:
        channels: dict[str, Path] = {}
        for led_dir in self.all_led_dirs:
            name = led_dir.name.lower()
            if not name.startswith("ite_8297:"):
                continue
            suffix = name.rsplit(":", 1)[-1]
            if suffix == "1":
                channels["red"] = led_dir
            elif suffix == "2":
                channels["green"] = led_dir
            elif suffix == "3":
                channels["blue"] = led_dir

        if len(channels) == 3:
            return channels
        return None

    def _read_channel_group_state(self, channels: dict[str, Path]) -> tuple[tuple[int, int, int], int]:
        red = max(0, common._read_int(channels["red"] / "brightness"))
        green = max(0, common._read_int(channels["green"] / "brightness"))
        blue = max(0, common._read_int(channels["blue"] / "brightness"))
        max_values = [
            max(1, common._read_int(channels["red"] / "max_brightness")),
            max(1, common._read_int(channels["green"] / "max_brightness")),
            max(1, common._read_int(channels["blue"] / "max_brightness")),
        ]
        level = max(
            red / max_values[0],
            green / max_values[1],
            blue / max_values[2],
        )
        brightness = int(round(level * 50))
        return (red, green, blue), max(0, min(50, brightness))

    def __post_init__(self):
        if not self.all_led_dirs:
            self.all_led_dirs = [self.primary_led_dir]

        # Primary paths for reading state
        self.brightness_path = self.primary_led_dir / "brightness"
        self.max_brightness_path = self.primary_led_dir / "max_brightness"

        # Discover lighting zones
        self._zones = []

        ite8297_channels = self._detect_ite8297_channel_group()
        if ite8297_channels is not None:
            self._zones.append(
                {
                    "type": "ite8297_channels",
                    "paths": ite8297_channels,
                    "led_dir": ite8297_channels["red"],
                }
            )
            try:
                self._channel_group_color, self._channel_group_brightness = self._read_channel_group_state(
                    ite8297_channels
                )
            except _CHANNEL_GROUP_STATE_ERRORS:
                self._channel_group_color = (0, 0, 0)
                self._channel_group_brightness = 0
            return

        # Case 1: Single directory, assume it might be System76 with multiple files
        if len(self.all_led_dirs) == 1:
            s76_paths = self._get_system76_color_paths(self.all_led_dirs[0])
            if s76_paths:
                # System76 typically layout is Left, Center, Right, (Extra)
                for p in s76_paths:
                    self._zones.append({"type": "file", "path": p, "led_dir": self.all_led_dirs[0]})
            else:
                self._zones.append({"type": "dir", "path": self.all_led_dirs[0], "led_dir": self.all_led_dirs[0]})
        else:
            # Case 2: Multiple directories (e.g. kbd_backlight_1, _2).
            # We assume the list passed in is already sorted intelligently by the backend
            # (usually by name, so _1 (left) comes before _2 (center)).
            for d in self.all_led_dirs:
                self._zones.append({"type": "dir", "path": d, "led_dir": d})

        # Pre-calculate key mapping if we have multiple zones
        if len(self._zones) > 1:
            width = BASE_IMAGE_SIZE[0]
            n_zones = len(self._zones)
            chunk_size = width / n_zones

            for key in REFERENCE_DEVICE_KEYS:
                # Use center of key to determine zone
                cx = key.rect[0] + (key.rect[2] / 2)
                z_idx = int(cx // chunk_size)
                # Clamp just in case
                z_idx = max(0, min(z_idx, n_zones - 1))
                self._key_to_zone_idx[key.key_id] = z_idx

    def capabilities(self) -> BackendCapabilities:
        # Report per-key support if we have multiple zones, to enable the Editor UI.
        # This gives users "Virtual 3-Zone" control.
        color_supported = False
        try:
            for zone in self._zones:
                led_dir = zone.get("led_dir")
                if not led_dir:
                    continue
                if zone.get("type") == "file":
                    color_supported = True
                    break
                if zone.get("type") == "ite8297_channels":
                    color_supported = True
                    break
                if (
                    self._supports_multicolor(led_dir)
                    or self._supports_color_attr(led_dir)
                    or self._supports_rgb_attr(led_dir)
                ):
                    color_supported = True
                    break
        except _CAPABILITY_PROBE_ERRORS:
            color_supported = False

        return BackendCapabilities(
            per_key=(len(self._zones) > 1),
            color=bool(color_supported),
            hardware_effects=False,
            palette=False,
        )

    def _max(self) -> int:
        try:
            m = common._read_int(self.max_brightness_path)
            return max(1, int(m))
        except _SYSFS_STATE_ERRORS:
            return 1

    def _read_sysfs_brightness(self) -> int:
        try:
            return max(0, int(common._read_int(self.brightness_path)))
        except _SYSFS_STATE_ERRORS:
            return 0

    def turn_off(self) -> None:
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self.get_brightness() <= 0

    def get_brightness(self) -> int:
        if self._channel_group_brightness is not None:
            return int(self._channel_group_brightness)

        # Normalize sysfs brightness into KeyRGB's "hardware" 0..50 scale.
        # We read only from the primary zone.
        sysfs_value = self._read_sysfs_brightness()
        max_value = self._max()
        return int(round((sysfs_value / max_value) * 50))

    def set_brightness(self, brightness: int) -> None:
        if any(zone.get("type") == "ite8297_channels" for zone in self._zones):
            self._channel_group_brightness = max(0, min(50, int(brightness)))
            if self._channel_group_color is None:
                self._channel_group_color = (0, 0, 0)
            for zone in self._zones:
                if zone.get("type") == "ite8297_channels":
                    self._set_zone_color(zone, self._channel_group_color, self._channel_group_brightness)
            return

        # Map KeyRGB's 0..50 brightness scale into sysfs range.
        b = max(0, min(50, int(brightness)))
        max_value = self._max()
        sysfs_value = int(round((b / 50) * max_value))

        # Debug logging (once). Logging is optional diagnostics, so a broken handler
        # should not block LED writes.
        try:
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                logger.info(
                    "backend.sysfs.set_brightness kb=%s sysfs=%s zones=%d max=%s",
                    b,
                    sysfs_value,
                    len(self._zones),
                    max_value,
                )
        except Exception:  # @quality-exception exception-transparency: debug brightness logging is a best-effort diagnostic boundary and logging handlers may raise arbitrary runtime errors
            pass

        # Apply to all zones
        for zone in self._zones:
            # Brightness is always on the led_dir, even for system76
            self._set_zone_brightness(zone["led_dir"], sysfs_value)

    def _set_zone_brightness(self, led_dir: Path, sysfs_value: int) -> None:
        brightness_path = led_dir / "brightness"
        try:
            common._write_int(brightness_path, sysfs_value)
            return
        except OSError:
            pass

        if not privileged.helper_supports_led_apply():
            # Only raise if it's the primary, otherwise we might just have a read-only rogue zone
            if led_dir == self.primary_led_dir:
                raise PermissionError(f"sysfs brightness not writable: {brightness_path}")
            return

        ok = privileged.run_led_apply(led=led_dir.name, brightness=int(sysfs_value), rgb=None)
        if not ok and led_dir == self.primary_led_dir:
            raise PermissionError(f"failed to write brightness via helper for LED {led_dir.name}")

    def _supports_multicolor(self, led_dir: Path) -> bool:
        """Check if device supports multi_intensity (Tuxedo/Clevo RGB)"""
        return (led_dir / "multi_intensity").exists()

    def _supports_color_attr(self, led_dir: Path) -> bool:
        """Check if device uses kernel driver with color attribute"""
        return (led_dir / "color").exists()

    def _supports_rgb_attr(self, led_dir: Path) -> bool:
        """Check if device uses generic 'rgb' attribute"""
        return (led_dir / "rgb").exists()

    def _get_system76_color_paths(self, led_dir: Path) -> list[Path]:
        """Return list of writable System76 color paths if present"""
        paths = []
        # System76 ACPI driver often exposes these for multi-zone RGB
        for name in ("color_left", "color_center", "color_right", "color_extra"):
            p = led_dir / name
            if p.exists():
                paths.append(p)
        return paths

    def set_color(self, color, *, brightness: int):
        """Enhanced color setting with multi_intensity and color attribute support"""
        # Logging is optional diagnostics, so a broken handler should not block LED writes.
        try:
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                r, g, b = color
                logger.info(
                    "backend.sysfs.set_color rgb=(%s,%s,%s) brightness=%s zones=%d",
                    r,
                    g,
                    b,
                    brightness,
                    len(self._zones),
                )
        except Exception:  # @quality-exception exception-transparency: debug color logging is a best-effort diagnostic boundary and logging handlers may raise arbitrary runtime errors
            pass

        for zone in self._zones:
            self._set_zone_color(zone, color, brightness)

    _set_zone_color = _set_zone_color_method
    _to_sysfs_brightness = _to_sysfs_brightness_method

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        # Implementation of Virtual 3-Zone (or N-zone) mapping

        # If we only have 1 zone, fallback to simple global color (average of all keys?)
        if len(self._zones) <= 1:
            # Simple average of all keys to find a "global" color
            if not color_map:
                return

            r_sum = g_sum = b_sum = count = 0
            for r, g, b in color_map.values():
                r_sum += r
                g_sum += g
                b_sum += b
                count += 1

            if count > 0:
                avg = (r_sum // count, g_sum // count, b_sum // count)
                self.set_color(avg, brightness=brightness)
            return

        # N-Zone logic: buckets
        zone_lists: list[list[tuple[int, int, int]]] = [[] for _ in self._zones]

        for key_id, color in color_map.items():
            z_idx = self._key_to_zone_idx.get(key_id)
            if z_idx is not None:
                zone_lists[z_idx].append(color)

        for i, colors in enumerate(zone_lists):
            if not colors:
                continue

            # Average color for this zone
            ar = sum(c[0] for c in colors) // len(colors)
            ag = sum(c[1] for c in colors) // len(colors)
            ab = sum(c[2] for c in colors) // len(colors)

            self._set_zone_color(self._zones[i], (ar, ag, ab), brightness)

    def set_effect(self, effect_data) -> None:
        # Not supported. No-op.
        return
