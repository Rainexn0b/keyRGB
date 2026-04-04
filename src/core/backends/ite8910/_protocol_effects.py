from __future__ import annotations

from typing import Any, NamedTuple


class EffectDesc(NamedTuple):
    """Describes how to build reports for a given effect."""

    animation: object | None = None
    random_cmd: object | None = None
    color_cmd: object | None = None
    slot_cmd: object | None = None
    slot_max: int = 0
    directions: tuple[str, ...] = ()


def build_effect_reports_impl(
    effect: object,
    *,
    effects: dict[Any, EffectDesc],
    colors: list[tuple[int, int, int]] | None,
    direction: str | None,
    build_animation_mode_report,
    report,
    rgb,
    color_custom: int,
    color_slot_base: int,
    preset_slot_base: int,
) -> list[bytes]:
    """Build the full report sequence for an effect."""

    desc = effects.get(effect)
    if not desc:
        return []

    colors = colors or []
    reports: list[bytes] = []

    if desc.animation:
        reports.append(build_animation_mode_report(desc.animation))

    if desc.color_cmd and colors:
        r, g, b = rgb(*colors[0])
        reports.append(report(desc.color_cmd, color_custom, r, g, b))

    if desc.random_cmd and not desc.animation and not colors:
        reports.append(report(desc.random_cmd, 0x00, 0x00, 0x00, 0x00))

    if not desc.slot_cmd:
        return reports

    direction_index = desc.directions.index(direction) if direction and direction in desc.directions else 0

    if desc.directions and colors:
        r, g, b = rgb(*colors[0])
        reports.append(report(desc.slot_cmd, color_slot_base + direction_index, r, g, b))

    if desc.directions and not colors:
        reports.append(report(desc.slot_cmd, preset_slot_base + direction_index, 0x00, 0x00, 0x00))

    if not desc.directions:
        for index, color in enumerate(colors[: desc.slot_max]):
            r, g, b = rgb(*color)
            reports.append(report(desc.slot_cmd, color_slot_base + index, r, g, b))

    return reports
