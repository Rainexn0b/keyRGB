from __future__ import annotations


def serialize_per_key_colors(color_map: dict) -> dict:
    """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""

    out: dict[str, list[int]] = {}
    if not isinstance(color_map, dict):
        return out

    for (row, col), color in color_map.items():
        try:
            r, g, b = color
            out[f"{int(row)},{int(col)}"] = [int(r), int(g), int(b)]
        except Exception:
            continue

    return out


def deserialize_per_key_colors(data: dict) -> dict:
    """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""

    out: dict[tuple[int, int], tuple[int, int, int]] = {}
    if not isinstance(data, dict):
        return out

    for k, v in data.items():
        try:
            row_s, col_s = str(k).split(",", 1)
            row = int(row_s.strip())
            col = int(col_s.strip())
            r, g, b = v
            out[(row, col)] = (int(r), int(g), int(b))
        except Exception:
            continue

    return out
