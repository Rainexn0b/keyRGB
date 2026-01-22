from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from ..base import KeyboardDevice
from . import common
from . import privileged

logger = logging.getLogger(__name__)


@dataclass
class SysfsLedKeyboardDevice(KeyboardDevice):
    brightness_path: Path
    max_brightness_path: Path
    led_dir: Path

    def _max(self) -> int:
        try:
            m = common._read_int(self.max_brightness_path)
            return max(1, int(m))
        except Exception:
            return 1

    def _read_sysfs_brightness(self) -> int:
        try:
            return max(0, int(common._read_int(self.brightness_path)))
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
        try:
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                logger.info(
                    "backend.sysfs.set_brightness kb=%s sysfs=%s path=%s max=%s",
                    b,
                    sysfs_value,
                    self.brightness_path,
                    max_value,
                )
        except Exception:
            pass
        try:
            common._write_int(self.brightness_path, sysfs_value)
            return
        except PermissionError:
            pass
        except Exception:
            # If direct write fails for other reasons, still allow helper.
            pass

        if not privileged.helper_supports_led_apply():
            raise PermissionError(f"sysfs brightness not writable: {self.brightness_path}")

        ok = privileged.run_led_apply(led=self.led_dir.name, brightness=int(sysfs_value), rgb=None)
        if not ok:
            raise PermissionError(f"failed to write brightness via helper for LED {self.led_dir.name}")

    def _supports_multicolor(self) -> bool:
        """Check if device supports multi_intensity (Tuxedo/Clevo RGB)"""
        multi_intensity_path = self.led_dir / "multi_intensity"
        return multi_intensity_path.exists()

    def _supports_color_attr(self) -> bool:
        """Check if device uses kernel driver with color attribute"""
        color_path = self.led_dir / "color"
        return color_path.exists()

    def _get_system76_color_paths(self) -> list[Path]:
        """Return list of writable System76 color paths if present"""
        paths = []
        # System76 ACPI driver often exposes these for multi-zone RGB
        for name in ("color_left", "color_center", "color_right", "color_extra"):
            p = self.led_dir / name
            if p.exists():
                paths.append(p)
        return paths

    def set_color(self, color, *, brightness: int):
        """Enhanced color setting with multi_intensity and color attribute support"""
        try:
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                r, g, b = color
                logger.info(
                    "backend.sysfs.set_color rgb=(%s,%s,%s) brightness=%s path=%s",
                    r,
                    g,
                    b,
                    brightness,
                    self.led_dir,
                )
        except Exception:
            pass
        r, g, b = color

        # Try multi_intensity first (Tuxedo/Clevo)
        if self._supports_multicolor():
            multi_intensity_path = self.led_dir / "multi_intensity"
            try:
                common._safe_write_text(multi_intensity_path, f"{r} {g} {b}\n")
                self.set_brightness(brightness)
                return
            except PermissionError:
                if privileged.helper_supports_led_apply() and privileged.run_led_apply(
                    led=self.led_dir.name,
                    brightness=int(round((max(0, min(50, int(brightness))) / 50) * self._max())),
                    rgb=(int(r), int(g), int(b)),
                ):
                    return
                raise

        # Try color attribute (ITE kernel driver)
        if self._supports_color_attr():
            hex_color = f"{int(r):02x}{int(g):02x}{int(b):02x}"
            color_path = self.led_dir / "color"
            try:
                common._safe_write_text(color_path, f"{hex_color}\n")
                self.set_brightness(brightness)
                return
            except PermissionError:
                if privileged.helper_supports_led_apply() and privileged.run_led_apply(
                    led=self.led_dir.name,
                    brightness=int(round((max(0, min(50, int(brightness))) / 50) * self._max())),
                    rgb=(int(r), int(g), int(b)),
                ):
                    return
                raise

        # Try System76 color paths
        s76_paths = self._get_system76_color_paths()
        if s76_paths:
            r, g, b = color
            hex_color = f"{r:02X}{g:02X}{b:02X}"
            for p in s76_paths:
                common._safe_write_text(p, f"{hex_color}\n")
            self.set_brightness(brightness)
            return

        # Fallback: brightness-only
        self.set_brightness(brightness)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        # Not supported. No-op to avoid crashing if legacy code attempts per-key.
        self.set_brightness(brightness)

    def set_effect(self, effect_data) -> None:
        # Not supported. No-op.
        return
