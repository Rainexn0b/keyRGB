from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Dict, Tuple


KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]

_LIGHTBAR_FLOAT_KEYS = ("length", "thickness", "dx", "dy", "inset")
_LAYOUT_TWEAK_DEFAULTS: Dict[str, float] = {
    "dx": 0.0,
    "dy": 0.0,
    "sx": 1.0,
    "sy": 1.0,
    "inset": 0.06,
}


def _normalize_secondary_color(raw: object) -> list[int] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        return None
    if not all(isinstance(channel, (int, float)) for channel in raw):
        return None
    return [max(0, min(255, int(channel))) for channel in raw]


def _normalize_secondary_enabled(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and raw in (0, 1):
        return bool(raw)
    return None


def _normalize_secondary_brightness(raw: object) -> int | None:
    if not isinstance(raw, (int, float)):
        return None
    return max(0, min(100, int(raw)))


def normalize_secondary_lighting(raw: object) -> Dict[str, object]:
    """Normalize a secondary-lighting payload without destructive migration.

    Unknown top-level fields, route keys, and entry fields are retained. The
    caller can distinguish a missing component because ``load_*`` returns
    ``None`` before invoking this normalizer, while an explicit empty ``areas``
    map remains present in the returned payload.
    """
    if not isinstance(raw, Mapping):
        return {"version": 1, "areas": {}}

    payload: Dict[str, object] = dict(raw)
    payload["version"] = 1
    raw_areas = raw.get("areas")
    areas: Dict[str, object] = {}
    if isinstance(raw_areas, Mapping):
        for raw_key, raw_entry in raw_areas.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                continue
            if not isinstance(raw_entry, Mapping):
                # Preserve unknown route data rather than silently deleting it.
                areas[raw_key] = raw_entry
                continue

            entry: Dict[str, object] = dict(raw_entry)
            if "enabled" in entry:
                enabled = _normalize_secondary_enabled(entry["enabled"])
                if enabled is None:
                    entry.pop("enabled", None)
                else:
                    entry["enabled"] = enabled
            if "color" in entry:
                color = _normalize_secondary_color(entry["color"])
                if color is None:
                    entry.pop("color", None)
                else:
                    entry["color"] = color
            if "brightness" in entry:
                brightness = _normalize_secondary_brightness(entry["brightness"])
                if brightness is None:
                    entry.pop("brightness", None)
                else:
                    entry["brightness"] = brightness
            areas[raw_key] = entry

    payload["areas"] = areas
    return payload


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def normalize_lightbar_overlay(
    raw: object, *, get_default_lightbar_overlay: Callable[..., object]
) -> Dict[str, bool | float]:
    out: Dict[str, bool | float] = dict(get_default_lightbar_overlay())  # type: ignore[call-overload]
    if isinstance(raw, dict):
        visible = raw.get("visible")
        if isinstance(visible, bool):
            out["visible"] = visible
        elif isinstance(visible, (int, float)):
            out["visible"] = bool(visible)

        for key in _LIGHTBAR_FLOAT_KEYS:
            value = raw.get(key)
            if isinstance(value, (int, float)):
                out[key] = float(value)

    out["length"] = _clamp(float(out.get("length", 0.72)), 0.20, 1.0)
    out["thickness"] = _clamp(float(out.get("thickness", 0.12)), 0.04, 0.40)
    out["dx"] = _clamp(float(out.get("dx", 0.0)), -0.50, 0.50)
    out["dy"] = _clamp(float(out.get("dy", 0.0)), -0.50, 0.50)
    out["inset"] = _clamp(float(out.get("inset", 0.04)), 0.0, 0.25)
    out["visible"] = bool(out.get("visible", True))
    return out


def parse_keymap_cell(raw: object) -> KeyCell | None:
    if isinstance(raw, str) and "," in raw:
        row_text, col_text = raw.split(",", 1)
        try:
            return (int(row_text), int(col_text))
        except (TypeError, ValueError):
            return None

    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        first, second = raw
        if isinstance(first, (list, tuple, dict)) or isinstance(second, (list, tuple, dict)):
            return None
        try:
            return (int(first), int(second))
        except (TypeError, ValueError):
            return None

    return None


def parse_keymap_cells(raw: object) -> KeyCells:
    single = parse_keymap_cell(raw)
    if single is not None:
        return (single,)

    if not isinstance(raw, (list, tuple)):
        return ()

    out: list[KeyCell] = []
    seen: set[KeyCell] = set()
    for item in raw:
        cell = parse_keymap_cell(item)
        if cell is None or cell in seen:
            continue
        seen.add(cell)
        out.append(cell)
    return tuple(out)


def encode_keymap_payload(keymap: Mapping[str, KeyCells]) -> Dict[str, str | list[str]]:
    payload: Dict[str, str | list[str]] = {}
    for key_id, raw_cells in sorted(keymap.items()):
        cells = parse_keymap_cells(raw_cells)
        if not cells:
            continue
        encoded = [f"{row},{col}" for row, col in cells]
        payload[key_id] = encoded[0] if len(encoded) == 1 else encoded
    return payload


def normalize_layout_global(raw: object) -> Dict[str, float]:
    out = dict(_LAYOUT_TWEAK_DEFAULTS)
    if isinstance(raw, dict):
        for key in _LAYOUT_TWEAK_DEFAULTS:
            value = raw.get(key)
            if isinstance(value, (int, float)):
                out[key] = float(value)
    out["inset"] = _clamp(float(out.get("inset", _LAYOUT_TWEAK_DEFAULTS["inset"])), 0.0, 0.20)
    return out


def encode_layout_global(tweaks: Mapping[str, float]) -> Dict[str, float]:
    return {key: float(tweaks.get(key, default)) for key, default in _LAYOUT_TWEAK_DEFAULTS.items()}


def parse_per_key_colors(raw: object) -> Dict[KeyCell, Tuple[int, int, int]]:
    out: Dict[KeyCell, Tuple[int, int, int]] = {}
    if not isinstance(raw, dict):
        return out

    for key, value in raw.items():
        try:
            row_text, col_text = str(key).split(",", 1)
            row = int(row_text.strip())
            col = int(col_text.strip())
            rr, gg, bb = value
            out[(row, col)] = (int(rr), int(gg), int(bb))
        except (TypeError, ValueError):
            continue
    return out


def encode_per_key_colors(colors: Mapping[KeyCell, Tuple[int, int, int]]) -> Dict[str, list[int]]:
    payload: Dict[str, list[int]] = {}
    for (row, col), rgb in colors.items():
        try:
            rr, gg, bb = rgb
            payload[f"{int(row)},{int(col)}"] = [int(rr), int(gg), int(bb)]
        except (TypeError, ValueError):
            continue
    return payload
