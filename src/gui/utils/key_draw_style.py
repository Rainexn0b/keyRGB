from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyDrawStyle:
    fill: str
    stipple: str
    text_fill: str
    outline: str
    width: int
    dash: tuple[int, ...]


def key_draw_style(
    *,
    mapped: bool,
    selected: bool,
    color: tuple[int, int, int] | None = None,
) -> KeyDrawStyle:
    """Compute a consistent key-rectangle style for keyboard UIs.

    Used by the per-key editor and keymap calibrator.
    """

    if not mapped:
        fill = ""
        stipple = ""
        text_fill = "#cfcfcf"
    elif color is None:
        fill = "#000000"
        stipple = "gray75"
        text_fill = "#e0e0e0"
    else:
        r, g, b = color
        fill = f"#{r:02x}{g:02x}{b:02x}"
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_fill = "#000000" if brightness > 128 else "#ffffff"
        stipple = "gray50"

    outline = "#00ffff" if selected else ("#777777" if mapped else "#8a8a8a")
    width = 3 if selected else 2
    dash = () if mapped else (3,)

    return KeyDrawStyle(
        fill=fill,
        stipple=stipple,
        text_fill=text_fill,
        outline=outline,
        width=width,
        dash=dash,
    )
