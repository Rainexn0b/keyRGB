from __future__ import annotations

import os
from pathlib import Path

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x6010, 0x7000, 0x7001)
DEFAULT_PRODUCT_ID = 0x7001
HIDRAW_PATH_ENV = "KEYRGB_ITE8233_HIDRAW_PATH"

PACKET_SIZE = 8
UI_BRIGHTNESS_MAX = 50
RAW_BRIGHTNESS_MAX = 100
RAW_SPEED_MIN = 1
RAW_SPEED_MAX = 10

# Descriptor-level facts taken from issue #5. Command bytes beyond these values
# are intentionally left undefined until traffic captures confirm them.
FEATURE_REPORT_ID = 0x5A
FEATURE_REPORT_SIZE = 16
VENDOR_USAGE_PAGE = 0xFF89

INTERRUPT_INTERFACE_INDEX = 1
INTERRUPT_IN_ENDPOINT = 0x81
INTERRUPT_OUT_ENDPOINT = 0x02

# Upstream-backed minimal 0x7001 packet set.
COMMAND_SET_COLOR = 0x14
COMMAND_SET_MODE = 0x08
COMMAND_OFF_STAGE_1 = 0x12
COMMAND_OFF_STAGE_2 = 0x08
COMMAND_OFF_STAGE_3 = 0x08
COMMAND_OFF_STAGE_4 = 0x1A

MODE_OFF = 0x00
MODE_DIRECT = 0x01
MODE_BREATHING = 0x02
MODE_WAVE = 0x03
MODE_BOUNCE = 0x04
MODE_MARQUEE = 0x05
MODE_SCAN = 0x06
MODE_FLASH = 0x11
COLOR_SLOT_COUNT = 7

FLASH_DIRECTION_NONE = 0x00
FLASH_DIRECTION_RIGHT = 0x01
FLASH_DIRECTION_LEFT = 0x02

SUPPORTED_EFFECT_MODES: tuple[int, ...] = (
    MODE_DIRECT,
    MODE_BREATHING,
    MODE_WAVE,
    MODE_BOUNCE,
    MODE_MARQUEE,
    MODE_SCAN,
)

_COLOR_VARIANT: dict[int, int] = {
    0x6010: 0x00,
    0x7000: 0x01,
    0x7001: 0x00,
}

_MODE_VARIANT: dict[int, int] = {
    0x6010: 0x02,
    0x7000: 0x21,
    0x7001: 0x22,
}

_MODE_APPLY_BYTE: dict[int, int] = {
    0x6010: 0x08,
    0x7000: 0x01,
    0x7001: 0x01,
}

_BREATHING_APPLY_BYTE: dict[int, int] = {
    0x6010: 0x08,
    0x7000: 0x08,
}

_WAVE_APPLY_BYTE: dict[int, int] = {
    0x7000: 0x01,
}

_BOUNCE_APPLY_BYTE: dict[int, int] = {
    0x7000: 0x08,
}

_CATCHUP_APPLY_BYTE: dict[int, int] = {
    0x7000: 0x01,
}

_FLASH_APPLY_BYTE: dict[int, int] = {
    0x6010: 0x08,
}

_TURN_OFF_STAGE_3: dict[int, bytes] = {
    0x6010: bytes((COMMAND_OFF_STAGE_3, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    0x7000: bytes((COMMAND_OFF_STAGE_3, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00)),
    0x7001: bytes((COMMAND_OFF_STAGE_3, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
}

_TURN_OFF_STAGE_4: dict[int, bytes] = {
    0x6010: bytes((COMMAND_OFF_STAGE_4, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    0x7000: bytes((COMMAND_OFF_STAGE_4, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    0x7001: bytes((COMMAND_OFF_STAGE_4, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
}

_COLOR_SCALE_QUIRK_SKUS = frozenset({"STEPOL1XA04", "STELLARIS1XI05", "STELLARIS17I06"})


def _sysfs_dmi_root() -> Path:
    return Path(os.environ.get("KEYRGB_SYSFS_DMI_ROOT", "/sys/class/dmi/id"))


def _product_sku() -> str:
    try:
        return (_sysfs_dmi_root() / "product_sku").read_text(encoding="utf-8").strip().upper()
    except OSError:
        return ""


def _apply_color_scaling_quirk(red: int, green: int, blue: int, *, product_id: int) -> tuple[int, int, int]:
    if product_id != 0x6010:
        return red, green, blue

    if _product_sku() not in _COLOR_SCALE_QUIRK_SKUS:
        return red, green, blue

    return red, (100 * green) // 255, (100 * blue) // 255


def normalize_product_id(product_id: int | None) -> int:
    value = DEFAULT_PRODUCT_ID if product_id is None else int(product_id)
    if value not in SUPPORTED_PRODUCT_IDS:
        raise ValueError(f"Unsupported ITE lightbar product id: 0x{value:04x}")
    return value


def clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))


def clamp_ui_brightness(value: int) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, int(value)))


def clamp_raw_brightness(value: int) -> int:
    return max(0, min(RAW_BRIGHTNESS_MAX, int(value)))


def clamp_raw_speed(value: int) -> int:
    return max(RAW_SPEED_MIN, min(RAW_SPEED_MAX, int(value)))


def raw_brightness_from_ui(value: int) -> int:
    level = clamp_ui_brightness(value)
    if level <= 0:
        return 0
    return clamp_raw_brightness(round(level / UI_BRIGHTNESS_MAX * RAW_BRIGHTNESS_MAX))


def raw_speed_from_ui(value: int) -> int:
    level = clamp_raw_speed(value)
    return (RAW_SPEED_MAX + RAW_SPEED_MIN) - level


def scale_color_for_brightness(color, brightness: int) -> tuple[int, int, int]:
    red, green, blue = color
    level = clamp_ui_brightness(brightness)
    if level <= 0:
        return (0, 0, 0)
    if level >= UI_BRIGHTNESS_MAX:
        return (clamp_channel(red), clamp_channel(green), clamp_channel(blue))

    scale = level / UI_BRIGHTNESS_MAX
    return (
        clamp_channel(round(int(red) * scale)),
        clamp_channel(round(int(green) * scale)),
        clamp_channel(round(int(blue) * scale)),
    )


def build_uniform_color_report(color, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    red, green, blue = (clamp_channel(channel) for channel in color)
    red, green, blue = _apply_color_scaling_quirk(red, green, blue, product_id=product_id)
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_COLOR
    packet[1] = _COLOR_VARIANT[product_id]
    packet[2] = 0x01
    packet[3] = red
    packet[4] = green
    packet[5] = blue
    return bytes(packet)


def breathing_supported(product_id: int) -> bool:
    return normalize_product_id(product_id) in _BREATHING_APPLY_BYTE


def wave_supported(product_id: int) -> bool:
    return normalize_product_id(product_id) in _WAVE_APPLY_BYTE


def bounce_supported(product_id: int) -> bool:
    return normalize_product_id(product_id) in _BOUNCE_APPLY_BYTE


def catchup_supported(product_id: int) -> bool:
    return normalize_product_id(product_id) in _CATCHUP_APPLY_BYTE


def flash_supported(product_id: int) -> bool:
    return normalize_product_id(product_id) in _FLASH_APPLY_BYTE


def build_color_slot_report(slot: int, color, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    slot_index = max(1, min(COLOR_SLOT_COUNT, int(slot)))
    red, green, blue = (clamp_channel(channel) for channel in color)
    red, green, blue = _apply_color_scaling_quirk(red, green, blue, product_id=product_id)

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_COLOR
    packet[1] = _COLOR_VARIANT[product_id]
    packet[2] = slot_index
    packet[3] = red
    packet[4] = green
    packet[5] = blue
    return bytes(packet)


def build_breathing_report(
    *, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID
) -> bytes:
    product_id = normalize_product_id(product_id)
    if product_id not in _BREATHING_APPLY_BYTE:
        raise ValueError(f"ITE lightbar breathing is not supported for product id 0x{product_id:04x}")

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = MODE_BREATHING
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _BREATHING_APPLY_BYTE[product_id]
    return bytes(packet)


def build_breathing_reports(
    color, *, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID
) -> tuple[bytes, ...]:
    product_id = normalize_product_id(product_id)
    if product_id not in _BREATHING_APPLY_BYTE:
        raise ValueError(f"ITE lightbar breathing is not supported for product id 0x{product_id:04x}")

    color_reports = tuple(
        build_color_slot_report(slot, color, product_id=product_id) for slot in range(1, COLOR_SLOT_COUNT + 1)
    )
    return (*color_reports, build_breathing_report(brightness=brightness, speed=speed, product_id=product_id))


def build_wave_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    if product_id not in _WAVE_APPLY_BYTE:
        raise ValueError(f"ITE lightbar wave is not supported for product id 0x{product_id:04x}")

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = MODE_WAVE
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _WAVE_APPLY_BYTE[product_id]
    return bytes(packet)


def build_bounce_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    if product_id not in _BOUNCE_APPLY_BYTE:
        raise ValueError(f"ITE lightbar bounce is not supported for product id 0x{product_id:04x}")

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = MODE_BOUNCE
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _BOUNCE_APPLY_BYTE[product_id]
    return bytes(packet)


def build_catchup_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    if product_id not in _CATCHUP_APPLY_BYTE:
        raise ValueError(f"ITE lightbar catchup is not supported for product id 0x{product_id:04x}")

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = MODE_MARQUEE
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _CATCHUP_APPLY_BYTE[product_id]
    return bytes(packet)


def build_flash_report(
    *, brightness: int, speed: int, direction: int = FLASH_DIRECTION_NONE, product_id: int = DEFAULT_PRODUCT_ID
) -> bytes:
    product_id = normalize_product_id(product_id)
    if product_id not in _FLASH_APPLY_BYTE:
        raise ValueError(f"ITE lightbar flash is not supported for product id 0x{product_id:04x}")

    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = MODE_FLASH
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _FLASH_APPLY_BYTE[product_id]
    packet[6] = int(direction) & 0xFF
    return bytes(packet)


def build_flash_reports(
    color, *, brightness: int, speed: int, direction: int = FLASH_DIRECTION_NONE, product_id: int = DEFAULT_PRODUCT_ID
) -> tuple[bytes, ...]:
    product_id = normalize_product_id(product_id)
    if product_id not in _FLASH_APPLY_BYTE:
        raise ValueError(f"ITE lightbar flash is not supported for product id 0x{product_id:04x}")

    color_reports = tuple(
        build_color_slot_report(slot, color, product_id=product_id) for slot in range(1, COLOR_SLOT_COUNT + 1)
    )
    return (*color_reports, build_flash_report(brightness=brightness, speed=speed, direction=direction, product_id=product_id))


def build_mode_report(*, mode: int, brightness: int, speed: int = RAW_SPEED_MIN, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = int(mode) & 0xFF
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = _MODE_APPLY_BYTE[product_id]
    return bytes(packet)


def build_brightness_report(brightness: int, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    return build_mode_report(mode=MODE_DIRECT, brightness=brightness, speed=RAW_SPEED_MIN, product_id=product_id)


def build_turn_off_reports(*, product_id: int = DEFAULT_PRODUCT_ID) -> tuple[bytes, bytes, bytes, bytes]:
    product_id = normalize_product_id(product_id)
    sequence: tuple[bytes, ...] = (
        bytes((COMMAND_OFF_STAGE_1, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((COMMAND_OFF_STAGE_2, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        _TURN_OFF_STAGE_3[product_id],
        _TURN_OFF_STAGE_4[product_id],
    )
    if product_id == 0x6010:
        return (
            build_uniform_color_report((0, 0, 0), product_id=product_id),
            build_brightness_report(0, product_id=product_id),
            *sequence,
        )
    return sequence


def build_feature_probe_report() -> bytes:
    packet = bytearray(FEATURE_REPORT_SIZE)
    packet[0] = FEATURE_REPORT_ID
    return bytes(packet)
