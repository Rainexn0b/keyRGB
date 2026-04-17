from __future__ import annotations

import os
from pathlib import Path

from . import _protocol_support

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x6010, 0x7000, 0x7001)
DEFAULT_PRODUCT_ID = 0x7001
HIDRAW_PATH_ENV = "KEYRGB_ITE8233_HIDRAW_PATH"

PACKET_SIZE = _protocol_support.PACKET_SIZE
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

COMMAND_SET_COLOR = _protocol_support.COMMAND_SET_COLOR
COMMAND_SET_MODE = _protocol_support.COMMAND_SET_MODE
COMMAND_OFF_STAGE_1 = _protocol_support.COMMAND_OFF_STAGE_1
COMMAND_OFF_STAGE_2 = _protocol_support.COMMAND_OFF_STAGE_2
COMMAND_OFF_STAGE_3 = _protocol_support.COMMAND_OFF_STAGE_3
COMMAND_OFF_STAGE_4 = _protocol_support.COMMAND_OFF_STAGE_4

MODE_OFF = _protocol_support.MODE_OFF
MODE_DIRECT = _protocol_support.MODE_DIRECT
MODE_BREATHING = _protocol_support.MODE_BREATHING
MODE_WAVE = _protocol_support.MODE_WAVE
MODE_BOUNCE = _protocol_support.MODE_BOUNCE
MODE_MARQUEE = _protocol_support.MODE_MARQUEE
MODE_SCAN = _protocol_support.MODE_SCAN
MODE_FLASH = _protocol_support.MODE_FLASH
COLOR_SLOT_COUNT = _protocol_support.COLOR_SLOT_COUNT

FLASH_DIRECTION_NONE = _protocol_support.FLASH_DIRECTION_NONE
FLASH_DIRECTION_RIGHT = _protocol_support.FLASH_DIRECTION_RIGHT
FLASH_DIRECTION_LEFT = _protocol_support.FLASH_DIRECTION_LEFT

SUPPORTED_EFFECT_MODES = _protocol_support.SUPPORTED_EFFECT_MODES

_COLOR_VARIANT = _protocol_support._COLOR_VARIANT
_MODE_VARIANT = _protocol_support._MODE_VARIANT
_MODE_APPLY_BYTE = _protocol_support._MODE_APPLY_BYTE
_BREATHING_APPLY_BYTE = _protocol_support._BREATHING_APPLY_BYTE
_WAVE_APPLY_BYTE = _protocol_support._WAVE_APPLY_BYTE
_BOUNCE_APPLY_BYTE = _protocol_support._BOUNCE_APPLY_BYTE
_CATCHUP_APPLY_BYTE = _protocol_support._CATCHUP_APPLY_BYTE
_FLASH_APPLY_BYTE = _protocol_support._FLASH_APPLY_BYTE
_TURN_OFF_STAGE_3 = _protocol_support._TURN_OFF_STAGE_3
_TURN_OFF_STAGE_4 = _protocol_support._TURN_OFF_STAGE_4

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


def _scaled_color(color, *, product_id: int) -> tuple[int, int, int]:
    red, green, blue = (clamp_channel(channel) for channel in color)
    return _apply_color_scaling_quirk(red, green, blue, product_id=product_id)


def _build_color_report(slot: int, color, *, product_id: int) -> bytes:
    return _protocol_support.build_color_packet(
        product_id=product_id,
        slot=slot,
        color=_scaled_color(color, product_id=product_id),
    )


def _effect_supported(product_id: int, apply_bytes: dict[int, int]) -> bool:
    return normalize_product_id(product_id) in apply_bytes


def _effect_apply_byte(product_id: int, apply_bytes: dict[int, int], effect_name: str) -> int:
    try:
        return apply_bytes[product_id]
    except KeyError:
        raise ValueError(f"ITE lightbar {effect_name} is not supported for product id 0x{product_id:04x}") from None


def _build_effect_mode_report(
    *,
    product_id: int,
    mode: int,
    brightness: int,
    speed: int,
    apply_bytes: dict[int, int],
    effect_name: str,
    direction: int | None = None,
) -> bytes:
    return _protocol_support.build_mode_packet(
        product_id=product_id,
        mode=mode,
        brightness=clamp_raw_brightness(brightness),
        speed=clamp_raw_speed(speed),
        apply_byte=_effect_apply_byte(product_id, apply_bytes, effect_name),
        direction=direction,
    )


def _build_color_reports(color, *, product_id: int) -> tuple[bytes, ...]:
    return tuple(build_color_slot_report(slot, color, product_id=product_id) for slot in range(1, COLOR_SLOT_COUNT + 1))


def build_uniform_color_report(color, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_color_report(0x01, color, product_id=product_id)


def breathing_supported(product_id: int) -> bool:
    return _effect_supported(product_id, _BREATHING_APPLY_BYTE)


def wave_supported(product_id: int) -> bool:
    return _effect_supported(product_id, _WAVE_APPLY_BYTE)


def bounce_supported(product_id: int) -> bool:
    return _effect_supported(product_id, _BOUNCE_APPLY_BYTE)


def catchup_supported(product_id: int) -> bool:
    return _effect_supported(product_id, _CATCHUP_APPLY_BYTE)


def flash_supported(product_id: int) -> bool:
    return _effect_supported(product_id, _FLASH_APPLY_BYTE)


def build_color_slot_report(slot: int, color, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    slot_index = max(1, min(COLOR_SLOT_COUNT, int(slot)))
    return _build_color_report(slot_index, color, product_id=product_id)


def build_breathing_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_effect_mode_report(
        product_id=product_id,
        mode=MODE_BREATHING,
        brightness=brightness,
        speed=speed,
        apply_bytes=_BREATHING_APPLY_BYTE,
        effect_name="breathing",
    )


def build_breathing_reports(
    color, *, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID
) -> tuple[bytes, ...]:
    product_id = normalize_product_id(product_id)
    mode_report = build_breathing_report(brightness=brightness, speed=speed, product_id=product_id)
    return (*_build_color_reports(color, product_id=product_id), mode_report)


def build_wave_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_effect_mode_report(
        product_id=product_id,
        mode=MODE_WAVE,
        brightness=brightness,
        speed=speed,
        apply_bytes=_WAVE_APPLY_BYTE,
        effect_name="wave",
    )


def build_bounce_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_effect_mode_report(
        product_id=product_id,
        mode=MODE_BOUNCE,
        brightness=brightness,
        speed=speed,
        apply_bytes=_BOUNCE_APPLY_BYTE,
        effect_name="bounce",
    )


def build_catchup_report(*, brightness: int, speed: int, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_effect_mode_report(
        product_id=product_id,
        mode=MODE_MARQUEE,
        brightness=brightness,
        speed=speed,
        apply_bytes=_CATCHUP_APPLY_BYTE,
        effect_name="catchup",
    )


def build_flash_report(
    *, brightness: int, speed: int, direction: int = FLASH_DIRECTION_NONE, product_id: int = DEFAULT_PRODUCT_ID
) -> bytes:
    product_id = normalize_product_id(product_id)
    return _build_effect_mode_report(
        product_id=product_id,
        mode=MODE_FLASH,
        brightness=brightness,
        speed=speed,
        apply_bytes=_FLASH_APPLY_BYTE,
        effect_name="flash",
        direction=direction,
    )


def build_flash_reports(
    color, *, brightness: int, speed: int, direction: int = FLASH_DIRECTION_NONE, product_id: int = DEFAULT_PRODUCT_ID
) -> tuple[bytes, ...]:
    product_id = normalize_product_id(product_id)
    mode_report = build_flash_report(brightness=brightness, speed=speed, direction=direction, product_id=product_id)
    return (*_build_color_reports(color, product_id=product_id), mode_report)


def build_mode_report(
    *, mode: int, brightness: int, speed: int = RAW_SPEED_MIN, product_id: int = DEFAULT_PRODUCT_ID
) -> bytes:
    product_id = normalize_product_id(product_id)
    return _protocol_support.build_mode_packet(
        product_id=product_id,
        mode=mode,
        brightness=clamp_raw_brightness(brightness),
        speed=clamp_raw_speed(speed),
        apply_byte=_MODE_APPLY_BYTE[product_id],
    )


def build_brightness_report(brightness: int, *, product_id: int = DEFAULT_PRODUCT_ID) -> bytes:
    return build_mode_report(mode=MODE_DIRECT, brightness=brightness, speed=RAW_SPEED_MIN, product_id=product_id)


def build_turn_off_reports(*, product_id: int = DEFAULT_PRODUCT_ID) -> tuple[bytes, ...]:
    product_id = normalize_product_id(product_id)
    sequence = _protocol_support.build_turn_off_sequence(product_id=product_id)
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
