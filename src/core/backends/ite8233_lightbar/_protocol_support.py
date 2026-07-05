from __future__ import annotations

PACKET_SIZE = 8

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


def build_color_packet(*, product_id: int, slot: int, color: tuple[int, int, int]) -> bytes:
    red, green, blue = color
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_COLOR
    packet[1] = _COLOR_VARIANT[product_id]
    packet[2] = slot
    packet[3] = red
    packet[4] = green
    packet[5] = blue
    return bytes(packet)


def build_mode_packet(
    *,
    product_id: int,
    mode: int,
    brightness: int,
    speed: int,
    apply_byte: int,
    direction: int | None = None,
) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = _MODE_VARIANT[product_id]
    packet[2] = int(mode) & 0xFF
    packet[3] = speed
    packet[4] = brightness
    packet[5] = apply_byte
    if direction is not None:
        packet[6] = int(direction) & 0xFF
    return bytes(packet)


def build_turn_off_sequence(*, product_id: int) -> tuple[bytes, ...]:
    return (
        bytes((COMMAND_OFF_STAGE_1, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((COMMAND_OFF_STAGE_2, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        _TURN_OFF_STAGE_3[product_id],
        _TURN_OFF_STAGE_4[product_id],
    )
