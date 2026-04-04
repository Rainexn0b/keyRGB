from __future__ import annotations

from pathlib import Path

from . import common
from . import privileged


def to_sysfs_brightness_method(self, brightness: int) -> int:
    level = max(0, min(50, int(brightness)))
    max_value = self._max()
    return int(round((level / 50) * max_value))


def set_zone_color_method(self, zone: dict, color, brightness: int):
    r, g, b = color
    led_dir: Path = zone["led_dir"]

    if zone["type"] == "ite8297_channels":
        level = max(0, min(50, int(brightness))) / 50 if int(brightness) > 0 else 0.0
        scaled = {
            "red": int(round(int(r) * level)),
            "green": int(round(int(g) * level)),
            "blue": int(round(int(b) * level)),
        }
        for channel_name, value in scaled.items():
            channel_dir = zone["paths"][channel_name]
            max_value = max(1, common._read_int(channel_dir / "max_brightness"))
            common._write_int(channel_dir / "brightness", max(0, min(max_value, int(value))))
        self._channel_group_color = (int(r), int(g), int(b))
        self._channel_group_brightness = max(0, min(50, int(brightness)))
        return

    if zone["type"] == "file":
        try:
            hex_color = f"{r:02X}{g:02X}{b:02X}"
            common._safe_write_text(zone["path"], f"{hex_color}\n")
            self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
            return
        except PermissionError:
            pass

    if self._supports_multicolor(led_dir):
        multi_intensity_path = led_dir / "multi_intensity"
        try:
            common._safe_write_text(multi_intensity_path, f"{r} {g} {b}\n")
            self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
            return
        except PermissionError:
            if privileged.helper_supports_led_apply() and privileged.run_led_apply(
                led=led_dir.name,
                brightness=self._to_sysfs_brightness(brightness),
                rgb=(int(r), int(g), int(b)),
            ):
                return
            if led_dir == self.primary_led_dir:
                raise

    if self._supports_color_attr(led_dir):
        hex_color = f"{int(r):02x}{int(g):02x}{int(b):02x}"
        color_path = led_dir / "color"
        try:
            common._safe_write_text(color_path, f"{hex_color}\n")
            self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
            return
        except PermissionError:
            if privileged.helper_supports_led_apply() and privileged.run_led_apply(
                led=led_dir.name,
                brightness=self._to_sysfs_brightness(brightness),
                rgb=(int(r), int(g), int(b)),
            ):
                return
            if led_dir == self.primary_led_dir:
                raise

    if self._supports_rgb_attr(led_dir):
        rgb_path = led_dir / "rgb"
        try:
            common._safe_write_text(rgb_path, f"{r} {g} {b}\n")
            self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
            return
        except PermissionError:
            if privileged.helper_supports_led_apply() and privileged.run_led_apply(
                led=led_dir.name,
                brightness=self._to_sysfs_brightness(brightness),
                rgb=(int(r), int(g), int(b)),
            ):
                return
            if led_dir == self.primary_led_dir:
                raise

    self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
