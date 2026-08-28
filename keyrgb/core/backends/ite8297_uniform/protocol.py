from __future__ import annotations

from keyrgb.core.effects import colors as _effects_colors

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x8297,)
HIDRAW_PATH_ENV = "KEYRGB_ITE8297_HIDRAW_PATH"

PACKET_SIZE = 64
UI_BRIGHTNESS_MAX = 50

# Public reference: the TUXEDO `ite_8297` kernel driver writes a 64-byte HID
# feature report beginning with `cc b0 01 01` followed by RGB values.
REPORT_ID = 0xCC
COMMAND_COLOR = 0xB0
COMMAND_DIRECT = 0x01
COMMAND_SUBDIRECT = 0x01


def clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))


def clamp_ui_brightness(value: int) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, int(value)))


# Re-export the backend-neutral shared helper (no duplicated logic).
scale_color_for_brightness = _effects_colors.scale_color_for_brightness


def build_uniform_color_report(color) -> bytes:
    red, green, blue = (clamp_channel(channel) for channel in color)
    packet = bytearray(PACKET_SIZE)
    packet[0] = REPORT_ID
    packet[1] = COMMAND_COLOR
    packet[2] = COMMAND_DIRECT
    packet[3] = COMMAND_SUBDIRECT
    packet[4] = red
    packet[5] = green
    packet[6] = blue
    return bytes(packet)
