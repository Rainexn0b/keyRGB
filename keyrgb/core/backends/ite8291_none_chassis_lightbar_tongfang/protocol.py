"""Isolated protocol constants and builders for the Tongfang ITE 8291 lightbar.

Authoritative evidence: OpenRGB ``Controllers/IonicoController`` for
``048d:6005`` (``DetectIonicoControllers``, ``IonicoController::SetMode``,
``IonicoController::SetColors``, and ``RGBController_Ionico::DeviceUpdateMode``).
This module is intentionally standalone: it must not import or reuse any sibling
backend's PID tables.

Descriptor-level facts below (usage page ``0xFF03`` / usage ``0x01``) come
from the OpenRGB detector registration only. They are exposed as *expected*
identifiers for probing and are not claimed to have been verified against
real sysfs HID descriptors.

OpenRGB 22-vs-65 inconsistency (documented, not worked around): OpenRGB
declares 22 LEDs for this device, but the direct output report is 65 bytes
(1 report-ID byte + 64 payload bytes). Only bytes 1..63 can hold complete
RGB triplets (21 triplets); byte 64 (index 64) is left zero. The 22nd LED
cannot be fully addressed inside this report, so no partial 22nd RGB value
is faked here.
"""

from __future__ import annotations

VENDOR_ID = 0x048D
PRODUCT_ID = 0x6005
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x6005,)
DEFAULT_PRODUCT_ID = 0x6005

HIDRAW_PATH_ENV = "KEYRGB_ITE8291_TONGFANG_LIGHTBAR_HIDRAW_PATH"

# Expected (OpenRGB detector) usage identifiers. Probe-only metadata; the
# hidraw match itself is VID/PID-based.
USAGE_PAGE = 0xFF03
USAGE = 0x01

# Report lengths include the leading report-ID byte.
FEATURE_REPORT_LENGTH = 9
OUTPUT_REPORT_LENGTH = 65

DECLARED_LED_COUNT = 22
# Complete RGB triplets that fit in output bytes 1..63.
ADDRESSABLE_TRIPLET_COUNT = 21

BRIGHTNESS_MIN = 0
BRIGHTNESS_MAX = 50
SPEED_MIN = 0
SPEED_MAX = 10

MODE_DIRECT = 0x33
MODE_BREATHING = 0x02
MODE_WAVE = 0x20
MODE_RAINDROPS = 0x0A

# Hardware effect color slots repeated per effect (slot IDs 1..7).
EFFECT_COLOR_SLOT_COUNT = 7

SUPPORTED_EFFECT_MODES: tuple[int, ...] = (MODE_BREATHING, MODE_WAVE, MODE_RAINDROPS)


def normalize_product_id(product_id: int | None) -> int:
    value = DEFAULT_PRODUCT_ID if product_id is None else int(product_id)
    if value not in SUPPORTED_PRODUCT_IDS:
        raise ValueError(f"Unsupported ITE 8291 Tongfang lightbar product id: 0x{value:04x}")
    return value


def clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))


def clamp_brightness(value: int) -> int:
    return max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, int(value)))


def clamp_speed(value: int) -> int:
    return max(SPEED_MIN, min(SPEED_MAX, int(value)))


def build_off_report() -> bytes:
    """Feature report that switches the lightbar off (OpenRGB exact bytes)."""
    return bytes((0x00, 0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))


def build_mode_report(*, mode: int, brightness: int, speed: int) -> bytes:
    """Feature mode report: ``00 08 02 MM SS BB 08 00 00`` (OpenRGB exact)."""
    return bytes(
        (
            0x00,
            0x08,
            0x02,
            int(mode) & 0xFF,
            clamp_speed(speed),
            clamp_brightness(brightness),
            0x08,
            0x00,
            0x00,
        )
    )


def build_direct_mode_report(*, brightness: int, speed: int = 0) -> bytes:
    """Direct-mode selector (mode ``0x33``) sent before the output frame."""
    return build_mode_report(mode=MODE_DIRECT, brightness=brightness, speed=speed)


def build_begin_report() -> bytes:
    """Feature report that begins a direct-frame transfer (OpenRGB exact)."""
    return bytes((0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))


def build_commit_report() -> bytes:
    """Feature report that commits a direct-frame transfer (OpenRGB exact)."""
    return bytes((0x00, 0x12, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00))


def build_effect_color_report(slot: int, color) -> bytes:
    """Single effect color slot: ``00 14 00 ID RR GG BB 00 00`` (OpenRGB exact)."""
    slot_id = max(1, min(EFFECT_COLOR_SLOT_COUNT, int(slot)))
    red, green, blue = (clamp_channel(channel) for channel in color)
    return bytes((0x00, 0x14, 0x00, slot_id, red, green, blue, 0x00, 0x00))


def build_effect_color_reports(color) -> tuple[bytes, ...]:
    """All 7 repeated effect color slots (IDs 1..7) for one uniform color."""
    return tuple(build_effect_color_report(slot, color) for slot in range(1, EFFECT_COLOR_SLOT_COUNT + 1))


def build_direct_frame(color) -> bytes:
    """65-byte direct output frame: report ID 0, then R,B,G triplets.

    Only complete triplets fitting bytes 1..63 are written (21 triplets);
    byte 64 (index 64) stays zero. See the module docstring for the
    OpenRGB 22-vs-65 inconsistency.
    """
    red, green, blue = (clamp_channel(channel) for channel in color)
    frame = bytearray(OUTPUT_REPORT_LENGTH)
    frame[0] = 0x00
    for index in range(ADDRESSABLE_TRIPLET_COUNT):
        base = 1 + (index * 3)
        frame[base] = red
        frame[base + 1] = blue
        frame[base + 2] = green
    # frame[64] intentionally left zero: no room for a 22nd full triplet.
    return bytes(frame)
