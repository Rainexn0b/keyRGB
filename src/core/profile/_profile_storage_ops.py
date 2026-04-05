from __future__ import annotations

from collections.abc import Callable
from typing import Dict, Tuple, cast


KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]


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

        for key in ("length", "thickness", "dx", "dy", "inset"):
            value = raw.get(key)
            if isinstance(value, (int, float)):
                out[key] = float(value)

    out["length"] = max(0.20, min(1.0, float(out.get("length", 0.72))))
    out["thickness"] = max(0.04, min(0.40, float(out.get("thickness", 0.12))))
    out["dx"] = max(-0.50, min(0.50, float(out.get("dx", 0.0))))
    out["dy"] = max(-0.50, min(0.50, float(out.get("dy", 0.0))))
    out["inset"] = max(0.0, min(0.25, float(out.get("inset", 0.04))))
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


def canonical_layout_identity(
    *,
    physical_layout: str | None,
    identity: object,
    slot_id_for_key_id: Callable[..., object],
    key_id_for_slot_id: Callable[..., object],
) -> str:
    raw_identity = str(identity or "").strip()
    if not raw_identity:
        return ""

    slot_id = slot_id_for_key_id(physical_layout or "auto", raw_identity)
    if slot_id:
        return str(slot_id)

    if key_id_for_slot_id(physical_layout or "auto", raw_identity):
        return raw_identity

    return raw_identity


def normalize_layout_per_key_tweaks(
    raw: object,
    *,
    physical_layout: str | None,
    canonical_layout_identity_fn: Callable[..., object],
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    if not isinstance(raw, dict):
        return out

    for identity, tweaks in raw.items():
        if not isinstance(identity, str) or not isinstance(tweaks, dict):
            continue

        normalized_identity = cast(
            str, canonical_layout_identity_fn(physical_layout=physical_layout, identity=identity)
        )
        if not normalized_identity:
            continue

        parsed: Dict[str, float] = {}
        for key in ("dx", "dy", "sx", "sy", "inset"):
            value = tweaks.get(key)
            if isinstance(value, (int, float)):
                parsed[key] = float(value)

        if not parsed:
            continue

        if "inset" in parsed:
            parsed["inset"] = max(0.0, min(0.20, float(parsed["inset"])))

        existing = dict(out.get(normalized_identity, {}))
        existing.update(parsed)
        out[normalized_identity] = existing

    return out


def normalize_layout_slot_overrides(
    raw: object, *, physical_layout: str | None, sanitize_layout_slot_overrides: Callable[..., object]
) -> Dict[str, Dict[str, object]]:
    return sanitize_layout_slot_overrides(raw, layout_id=physical_layout)  # type: ignore[return-value]


def normalize_keymap(
    raw: object,
    *,
    physical_layout: str | None,
    canonical_layout_identity_fn: Callable[..., object],
) -> Dict[str, KeyCells]:
    out: Dict[str, KeyCells] = {}
    if not isinstance(raw, dict):
        return out

    for identity, raw_cells in raw.items():
        if not isinstance(identity, str):
            continue

        normalized_identity = cast(
            str, canonical_layout_identity_fn(physical_layout=physical_layout, identity=identity)
        )
        if not normalized_identity:
            continue

        cells = parse_keymap_cells(raw_cells)
        if not cells:
            continue

        merged: list[KeyCell] = list(out.get(normalized_identity, ()))
        seen = set(merged)
        for cell in cells:
            if cell in seen:
                continue
            seen.add(cell)
            merged.append(cell)
        out[normalized_identity] = tuple(merged)

    return out


def load_keymap(
    *,
    name: str | None,
    physical_layout: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    get_default_keymap: Callable[..., object],
    normalize_keymap_fn: Callable[..., object],
) -> Dict[str, KeyCells]:
    raw = read_json(paths_for(name).keymap)  # type: ignore[attr-defined]
    if raw is None:
        raw = get_default_keymap(physical_layout)
    return normalize_keymap_fn(raw, physical_layout=physical_layout)  # type: ignore[return-value]


def save_keymap(
    *,
    keymap: Dict[str, KeyCells],
    name: str | None,
    physical_layout: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
    normalize_keymap_fn: Callable[..., object],
) -> None:
    payload = {}
    for key_id, raw_cells in sorted(normalize_keymap_fn(keymap or {}, physical_layout=physical_layout).items()):  # type: ignore[attr-defined]
        cells = parse_keymap_cells(raw_cells)
        if not cells:
            continue
        encoded = [f"{row},{col}" for row, col in cells]
        payload[key_id] = encoded[0] if len(encoded) == 1 else encoded
    write_json_atomic(paths_for(name).keymap, payload)  # type: ignore[attr-defined]


def load_layout_global(
    *,
    name: str | None,
    physical_layout: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    get_default_layout_tweaks: Callable[..., object],
) -> Dict[str, float]:
    raw = read_json(paths_for(name).layout_global)  # type: ignore[attr-defined]
    if raw is None:
        raw = get_default_layout_tweaks(physical_layout)

    out = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    if isinstance(raw, dict):
        for key in list(out.keys()):
            value = raw.get(key)
            if isinstance(value, (int, float)):
                out[key] = float(value)
    out["inset"] = max(0.0, min(0.20, float(out.get("inset", 0.06))))
    return out


def save_layout_global(
    *,
    tweaks: Dict[str, float],
    name: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
) -> None:
    payload = {
        "dx": float(tweaks.get("dx", 0.0)),
        "dy": float(tweaks.get("dy", 0.0)),
        "sx": float(tweaks.get("sx", 1.0)),
        "sy": float(tweaks.get("sy", 1.0)),
        "inset": float(tweaks.get("inset", 0.06)),
    }
    write_json_atomic(paths_for(name).layout_global, payload)  # type: ignore[attr-defined]


def load_layout_per_key(
    *,
    name: str | None,
    physical_layout: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    get_default_per_key_tweaks: Callable[..., object],
    normalize_layout_per_key_tweaks_fn: Callable[..., object],
) -> Dict[str, Dict[str, float]]:
    raw = read_json(paths_for(name).layout_per_key)  # type: ignore[attr-defined]
    if raw is None:
        raw = get_default_per_key_tweaks(physical_layout)
    return normalize_layout_per_key_tweaks_fn(raw, physical_layout=physical_layout)  # type: ignore[return-value]


def save_layout_per_key(
    *,
    per_key: Dict[str, Dict[str, float]],
    name: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
    normalize_layout_per_key_tweaks_fn: Callable[..., object],
) -> None:
    write_json_atomic(
        paths_for(name).layout_per_key,  # type: ignore[attr-defined]
        normalize_layout_per_key_tweaks_fn(per_key or {}, physical_layout=None),  # type: ignore[attr-defined]
    )


def load_lightbar_overlay(
    *,
    name: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    get_default_lightbar_overlay: Callable[..., object],
    normalize_lightbar_overlay_fn: Callable[..., object],
) -> Dict[str, bool | float]:
    raw = read_json(paths_for(name).lightbar_overlay)  # type: ignore[attr-defined]
    if raw is None:
        raw = get_default_lightbar_overlay()
    return normalize_lightbar_overlay_fn(raw)  # type: ignore[return-value]


def save_lightbar_overlay(
    *,
    overlay: Dict[str, bool | float],
    name: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
    normalize_lightbar_overlay_fn: Callable[..., object],
) -> Dict[str, bool | float]:
    payload = normalize_lightbar_overlay_fn(overlay)
    write_json_atomic(paths_for(name).lightbar_overlay, payload)  # type: ignore[attr-defined]
    return payload  # type: ignore[return-value]


def load_layout_slots(
    *,
    name: str | None,
    physical_layout: str | None,
    load_layout_slot_overrides: Callable[..., object],
    normalize_layout_slot_overrides_fn: Callable[..., object],
) -> Dict[str, Dict[str, object]]:
    return normalize_layout_slot_overrides_fn(  # type: ignore[return-value]
        load_layout_slot_overrides(physical_layout or "auto", prior_profile_name=name),
        physical_layout=physical_layout,
    )


def save_layout_slots(
    *,
    layout_slots: Dict[str, Dict[str, object]],
    name: str | None,
    physical_layout: str | None,
    save_layout_slot_overrides: Callable[..., object],
    normalize_layout_slot_overrides_fn: Callable[..., object],
) -> Dict[str, Dict[str, object]]:
    return save_layout_slot_overrides(  # type: ignore[return-value]
        physical_layout or "auto",
        normalize_layout_slot_overrides_fn(layout_slots, physical_layout=physical_layout),
    )


def load_per_key_colors(
    *,
    name: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    safe_profile_name: Callable[..., object],
    default_colors: Dict[Tuple[int, int], Tuple[int, int, int]],
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    raw = read_json(paths_for(name).per_key_colors)  # type: ignore[attr-defined]
    if raw is None:
        prof = safe_profile_name(name or "")
        if prof == "dark":
            return {key: (0, 0, 0) for key in default_colors.keys()}
        if prof == "dim":
            return {key: (255, 255, 255) for key in default_colors.keys()}
        return default_colors.copy()

    out: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
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


def save_per_key_colors(
    *,
    colors: Dict[Tuple[int, int], Tuple[int, int, int]],
    name: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
) -> None:
    payload: Dict[str, list[int]] = {}
    for (row, col), rgb in (colors or {}).items():
        try:
            rr, gg, bb = rgb
            payload[f"{int(row)},{int(col)}"] = [int(rr), int(gg), int(bb)]
        except (TypeError, ValueError):
            continue
    write_json_atomic(paths_for(name).per_key_colors, payload)  # type: ignore[attr-defined]
