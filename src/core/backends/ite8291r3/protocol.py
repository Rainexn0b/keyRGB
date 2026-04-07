from __future__ import annotations

from collections.abc import Sequence

VENDOR_ID = 0x048D
PRODUCT_IDS: list[int] = [0x6004, 0x6006, 0x600B, 0xCE00]
REV_NUMBER = 0x0003

NUM_ROWS = 6
NUM_COLS = 21

ROW_BUFFER_LEN = (3 * NUM_COLS) + 2
ROW_RED_OFFSET = 1 + (2 * NUM_COLS)
ROW_GREEN_OFFSET = 1 + (1 * NUM_COLS)
ROW_BLUE_OFFSET = 1 + (0 * NUM_COLS)

UI_BRIGHTNESS_MAX = 50
USER_MODE_EFFECT = 0x33


class Commands:
    SET_EFFECT = 0x08
    SET_BRIGHTNESS = 0x09
    SET_PALETTE_COLOR = 0x14
    SET_ROW_INDEX = 0x16
    GET_FW_VERSION = 0x80
    GET_EFFECT = 0x88


class EffectAttrs:
    EFFECT = 0
    SPEED = 1
    BRIGHTNESS = 2
    COLOR = 3
    DIRECTION = 4
    REACTIVE = 4
    SAVE = 5


colors = {
    "none": 0,
    "red": 1,
    "orange": 2,
    "yellow": 3,
    "green": 4,
    "blue": 5,
    "teal": 6,
    "purple": 7,
    "random": 8,
}

directions = {
    "none": 0,
    "right": 1,
    "left": 2,
    "up": 3,
    "down": 4,
}

DEFAULT_PALETTE: dict[int, tuple[int, int, int]] = {
    1: (255, 0, 0),
    2: (255, 28, 0),
    3: (255, 119, 0),
    4: (0, 255, 0),
    5: (0, 0, 255),
    6: (0, 255, 255),
    7: (255, 0, 255),
}


def clamp_channel(value: object) -> int:
    return max(0, min(255, int(value)))


def clamp_ui_brightness(value: object) -> int:
    return max(0, min(UI_BRIGHTNESS_MAX, int(value)))


def build_control_report(*payload: object) -> bytes:
    values = [int(value) & 0xFF for value in payload]
    if len(values) < 8:
        values.extend([0] * (8 - len(values)))
    return bytes(values[:8])


def build_set_effect_report(
    *,
    control: int,
    effect: int = 0,
    speed: int = 0,
    brightness: int = 0,
    color: int = 0,
    direction_or_reactive: int = 0,
    save: int = 0,
) -> bytes:
    return build_control_report(
        Commands.SET_EFFECT,
        control,
        effect,
        speed,
        brightness,
        color,
        direction_or_reactive,
        save,
    )


def build_set_brightness_report(brightness: int) -> bytes:
    return build_control_report(Commands.SET_BRIGHTNESS, 0x02, clamp_ui_brightness(brightness))


def build_set_palette_color_report(slot: int, color_value) -> bytes:
    red, green, blue = color_value
    return build_control_report(
        Commands.SET_PALETTE_COLOR,
        0x00,
        int(slot),
        clamp_channel(red),
        clamp_channel(green),
        clamp_channel(blue),
    )


def build_set_row_index_report(row_idx: int) -> bytes:
    row = int(row_idx)
    if row < 0 or row >= NUM_ROWS:
        raise ValueError(f"row_idx must be between 0 and {NUM_ROWS - 1} inclusive")
    return build_control_report(Commands.SET_ROW_INDEX, 0x00, row)


def build_get_fw_version_report() -> bytes:
    return build_control_report(Commands.GET_FW_VERSION)


def build_get_effect_report() -> bytes:
    return build_control_report(Commands.GET_EFFECT)


def build_row_data_report(colors_for_row: Sequence[object]) -> bytes:
    if len(colors_for_row) != NUM_COLS:
        raise ValueError(f"row must contain exactly {NUM_COLS} colors")

    payload = bytearray(ROW_BUFFER_LEN)
    for index, color_value in enumerate(colors_for_row):
        try:
            red, green, blue = color_value  # type: ignore[misc]
        except (TypeError, ValueError) as exc:
            raise ValueError("row colors must be RGB 3-tuples") from exc
        payload[ROW_RED_OFFSET + index] = clamp_channel(red)
        payload[ROW_GREEN_OFFSET + index] = clamp_channel(green)
        payload[ROW_BLUE_OFFSET + index] = clamp_channel(blue)
    return bytes(payload)


def build_uniform_row_data_report(color_value) -> bytes:
    return build_row_data_report([color_value for _ in range(NUM_COLS)])


def effect(effect_id: int, args: dict[str, tuple[int, int]] | None = None):
    args = dict(args or {})
    max_arg_idx = max((item[0] for item in args.values()), default=-1)

    def build(**kwargs: object) -> list[int]:
        payload = [0] * max(1, max_arg_idx + 1)
        for key, (index, default) in args.items():
            payload[index] = int(default)

        for key, value in kwargs.items():
            if key not in args:
                raise ValueError(f"'{key}' attr is not needed by effect")
            payload[args[key][0]] = int(value)

        payload[EffectAttrs.EFFECT] = int(effect_id)
        return payload

    return build


effects = {
    "breathing": effect(
        0x02,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "wave": effect(
        0x03,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "direction": (EffectAttrs.DIRECTION, directions["right"]),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "random": effect(
        0x04,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "reactive": (EffectAttrs.REACTIVE, 0),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "rainbow": effect(
        0x05,
        {
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "ripple": effect(
        0x06,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "reactive": (EffectAttrs.REACTIVE, 0),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "marquee": effect(
        0x09,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "raindrop": effect(
        0x0A,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "aurora": effect(
        0x0E,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "reactive": (EffectAttrs.REACTIVE, 0),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
    "fireworks": effect(
        0x11,
        {
            "speed": (EffectAttrs.SPEED, 5),
            "brightness": (EffectAttrs.BRIGHTNESS, 25),
            "color": (EffectAttrs.COLOR, colors["random"]),
            "reactive": (EffectAttrs.REACTIVE, 0),
            "save": (EffectAttrs.SAVE, 0),
        },
    ),
}