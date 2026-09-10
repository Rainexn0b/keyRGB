"""Preview journal model: schema, validation, and snapshot type."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeGuard

logger = logging.getLogger(__name__)

PREVIEW_JOURNAL_FILENAME = "calibrator-preview-journal.json"
PREVIEW_JOURNAL_VERSION = 1

_SNAPSHOT_FIELDS = ("effect", "speed", "brightness", "color", "per_key_colors")

_BRIGHTNESS_MIN = 0
_BRIGHTNESS_MAX = 50
_SPEED_MIN = 0
_SPEED_MAX = 10


class PreviewConfigProtocol(Protocol):
    """Lighting state the calibrator preview mutates through ``Config``.

    Member types mirror ``Config``'s declared types exactly (protocol data
    members are invariant), so a real ``Config`` satisfies this protocol.
    """

    CONFIG_DIR: Path
    effect: str
    speed: int
    brightness: int
    color: tuple
    per_key_colors: dict


@dataclass(frozen=True)
class PreviewSnapshot:
    """A fully validated preview journal payload."""

    effect: str
    speed: int
    brightness: int
    color: tuple[int, int, int]
    per_key_colors: dict[tuple[int, int], tuple[int, int, int]]


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _validated_channel(value: object) -> int | None:
    if not _is_int(value) or not 0 <= value <= 255:
        return None
    return value


def _validated_color(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    channels = [_validated_channel(channel) for channel in value]
    if any(channel is None for channel in channels):
        return None
    red, green, blue = channels
    assert red is not None and green is not None and blue is not None
    return (red, green, blue)


def _validated_cell_key(raw_cell: object) -> tuple[int, int] | None:
    if not isinstance(raw_cell, str) or "," not in raw_cell:
        return None
    row_text, _, col_text = raw_cell.partition(",")
    try:
        row, col = int(row_text.strip()), int(col_text.strip())
    except (TypeError, ValueError):
        return None
    if row < 0 or col < 0:
        return None
    return (row, col)


def _validated_per_key_map(raw: object) -> dict[tuple[int, int], tuple[int, int, int]] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[tuple[int, int], tuple[int, int, int]] = {}
    for raw_cell, raw_color in raw.items():
        cell = _validated_cell_key(raw_cell)
        color = _validated_color(raw_color)
        if cell is None or color is None:
            return None
        out[cell] = color
    return out


def validate_journal_payload(payload: object) -> PreviewSnapshot | None:
    """Narrowly validate a raw journal document.

    Returns a :class:`PreviewSnapshot` when every field (including
    ``version``) is well-formed, otherwise ``None``.  A single malformed
    field makes the whole journal unusable so recovery never applies
    half-validated lighting state.
    """

    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    if not _is_int(version) or version != PREVIEW_JOURNAL_VERSION:
        return None
    effect = payload.get("effect")
    if not isinstance(effect, str) or not effect.strip():
        return None
    speed = payload.get("speed")
    if not _is_int(speed) or not _SPEED_MIN <= speed <= _SPEED_MAX:
        return None
    brightness = payload.get("brightness")
    if not _is_int(brightness) or not _BRIGHTNESS_MIN <= brightness <= _BRIGHTNESS_MAX:
        return None
    color = _validated_color(payload.get("color"))
    if color is None:
        return None
    per_key_colors = _validated_per_key_map(payload.get("per_key_colors"))
    if per_key_colors is None:
        return None
    return PreviewSnapshot(
        effect=effect,
        speed=speed,
        brightness=brightness,
        color=color,
        per_key_colors=per_key_colors,
    )


def journal_snapshot_fields() -> tuple[str, ...]:
    """Return the lighting field names covered by the journal (for tests)."""

    return _SNAPSHOT_FIELDS
