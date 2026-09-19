from __future__ import annotations

from collections.abc import Callable, Mapping

_LAYER_STATE_EXCEPTIONS = (AttributeError, LookupError, RuntimeError, TypeError, ValueError)


def _rgb_channels_from_value(value):
    """Coerce one per-key color entry to integer RGB channels.

    Accepts the canonical ``(r, g, b)`` triple and single-element nesting such
    as ``((r, g, b),)`` produced by some per-key payloads.
    """

    while isinstance(value, (tuple, list)) and len(value) == 1 and isinstance(value[0], (tuple, list)):
        value = value[0]
    red, green, blue = value
    return (int(red), int(green), int(blue))


def has_nonempty_per_key_base(per_key_colors: object | None) -> bool:
    """Return True when a usable saved per-key base map exists."""

    if per_key_colors is None:
        return False

    try:
        return len(per_key_colors) > 0  # type: ignore[arg-type]
    except _LAYER_STATE_EXCEPTIONS:
        return False


def render_effect_from_selected_effect(*, selected_effect: str, per_key_colors: object | None) -> str:
    """Map the selected effect layer to the runtime render effect.

    The canonical lighting stack is:
    - selected effect layer
    - brightness layer
    - base per-key color layer

    When no tertiary effect is selected, a non-empty base map should render as
    static per-key output instead of falling back to uniform hardware color.
    """

    effect = str(selected_effect or "none") or "none"
    if effect == "none" and has_nonempty_per_key_base(per_key_colors):
        return "perkey"
    return effect


def resolve_render_effect(
    *,
    selected_effect: str | None,
    per_key_colors: object | None,
    resolve_effect_name_fn: Callable[[str], str],
) -> str:
    """Resolve the selected effect first, then apply base-layer fallback rules."""

    resolved_selected = resolve_effect_name_fn(str(selected_effect or "none")) or "none"
    return render_effect_from_selected_effect(
        selected_effect=resolved_selected,
        per_key_colors=per_key_colors,
    )


def uniform_color_from_per_key_map(per_key_colors: object | None) -> tuple[int, int, int] | None:
    """Return the integer mean color across a per-key map, or None when empty.

    Mirrors the zone-device fallback rendering (sum/count integer division per
    channel) so a uniform software profile and the derived hardware color agree.
    """

    if not isinstance(per_key_colors, Mapping):
        return None

    red = green = blue = count = 0
    try:
        for color in per_key_colors.values():
            r, g, b = _rgb_channels_from_value(color)
            red += r
            green += g
            blue += b
            count += 1
    except _LAYER_STATE_EXCEPTIONS:
        return None

    if count <= 0:
        return None
    return (red // count, green // count, blue // count)


def _cell_column(key: object) -> int | None:
    if isinstance(key, tuple) and len(key) == 2:
        try:
            return int(key[1])
        except (TypeError, ValueError):
            return None
    return None


def bucket_color_map_to_zones(
    per_key_colors: object | None,
    *,
    zone_count: int,
    source_cols: int | None = None,
) -> dict[tuple[int, int], tuple[int, int, int]] | None:
    """Project a keyboard-sized color map onto a 1xN zone row.

    Column bands match reactive zone projection: ``col * zone_count // source_cols``.
    Returns None when the map is empty or unreadable.
    """

    if not isinstance(per_key_colors, Mapping) or int(zone_count) <= 0:
        return None

    samples: list[tuple[int, tuple[int, int, int]]] = []
    inferred_cols = 0
    try:
        for key, color in per_key_colors.items():
            column = _cell_column(key)
            if column is None:
                continue
            inferred_cols = max(inferred_cols, column + 1)
            samples.append((column, _rgb_channels_from_value(color)))
    except _LAYER_STATE_EXCEPTIONS:
        return None

    width = max(1, int(source_cols) if source_cols else inferred_cols)
    buckets: list[list[tuple[int, int, int]]] = [[] for _ in range(int(zone_count))]
    for column, rgb in samples:
        zone = min(int(zone_count) - 1, max(0, column * int(zone_count) // width))
        buckets[zone].append(rgb)

    out: dict[tuple[int, int], tuple[int, int, int]] = {}
    for zone, zone_samples in enumerate(buckets):
        if not zone_samples:
            continue
        count = len(zone_samples)
        out[(0, zone)] = (
            sum(sample[0] for sample in zone_samples) // count,
            sum(sample[1] for sample in zone_samples) // count,
            sum(sample[2] for sample in zone_samples) // count,
        )
    return out or None


def color_map_for_geometry(
    per_key_colors: object | None,
    *,
    rows: int,
    cols: int,
    source_cols: int | None = None,
) -> Mapping[object, object] | None:
    """Return a color map that fits ``rows x cols``, bucketing a wider keyboard map."""

    if not isinstance(per_key_colors, Mapping) or not per_key_colors:
        return None
    if int(rows) == 1 and int(cols) > 1:
        widest = 0
        for key in per_key_colors:
            column = _cell_column(key)
            if column is not None:
                widest = max(widest, column + 1)
        if widest > int(cols):
            return bucket_color_map_to_zones(
                per_key_colors,
                zone_count=int(cols),
                source_cols=source_cols or widest,
            )
    return per_key_colors


def zone_cells_for_column(
    *,
    num_rows: int,
    num_cols: int,
    zone_count: int,
    column: int,
) -> tuple[tuple[int, int], ...]:
    """Return every cell that shares ``column``'s zone band."""

    if int(zone_count) <= 1 or int(num_cols) <= 0 or int(num_rows) <= 0:
        return ((0, int(column)),)
    zone = min(int(zone_count) - 1, max(0, int(column) * int(zone_count) // int(num_cols)))
    return tuple(
        (row, col)
        for row in range(int(num_rows))
        for col in range(int(num_cols))
        if min(int(zone_count) - 1, max(0, col * int(zone_count) // int(num_cols))) == zone
    )
