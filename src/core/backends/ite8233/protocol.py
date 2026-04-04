from __future__ import annotations

VENDOR_ID = 0x048D
SUPPORTED_PRODUCT_IDS: tuple[int, ...] = (0x7001,)
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

SUPPORTED_EFFECT_MODES: tuple[int, ...] = (
    MODE_DIRECT,
    MODE_BREATHING,
    MODE_WAVE,
    MODE_BOUNCE,
    MODE_MARQUEE,
    MODE_SCAN,
)


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


def build_uniform_color_report(color) -> bytes:
    red, green, blue = (clamp_channel(channel) for channel in color)
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_COLOR
    packet[1] = 0x00
    packet[2] = 0x01
    packet[3] = red
    packet[4] = green
    packet[5] = blue
    return bytes(packet)


def build_mode_report(*, mode: int, brightness: int, speed: int = RAW_SPEED_MIN) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0] = COMMAND_SET_MODE
    packet[1] = 0x22
    packet[2] = int(mode) & 0xFF
    packet[3] = clamp_raw_speed(speed)
    packet[4] = clamp_raw_brightness(brightness)
    packet[5] = 0x01
    return bytes(packet)


def build_brightness_report(brightness: int) -> bytes:
    return build_mode_report(mode=MODE_DIRECT, brightness=brightness, speed=RAW_SPEED_MIN)


def build_turn_off_reports() -> tuple[bytes, bytes, bytes, bytes]:
    return (
        bytes((COMMAND_OFF_STAGE_1, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((COMMAND_OFF_STAGE_2, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((COMMAND_OFF_STAGE_3, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
        bytes((COMMAND_OFF_STAGE_4, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)),
    )


def build_feature_probe_report() -> bytes:
    packet = bytearray(FEATURE_REPORT_SIZE)
    packet[0] = FEATURE_REPORT_ID
    return bytes(packet)
