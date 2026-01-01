from __future__ import annotations


def resize_edges_for_point_in_bbox(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    cx: float,
    cy: float,
    thresh: float = 8.0,
) -> str:
    """Return which edges should resize based on pointer proximity.

    Returns a string containing any of: l, r, t, b.
    """

    edges = ""
    if (y1 - thresh) <= cy <= (y2 + thresh):
        if abs(cx - x1) <= thresh:
            edges += "l"
        if abs(cx - x2) <= thresh:
            edges += "r"
    if (x1 - thresh) <= cx <= (x2 + thresh):
        if abs(cy - y1) <= thresh:
            edges += "t"
        if abs(cy - y2) <= thresh:
            edges += "b"
    return edges


def cursor_for_edges(edges: str) -> str:
    # Tk cursor names vary by platform; these work well on Linux.
    if ("l" in edges or "r" in edges) and ("t" in edges or "b" in edges):
        # Diagonal resize
        if ("l" in edges and "t" in edges) or ("r" in edges and "b" in edges):
            return "top_left_corner"
        return "top_right_corner"
    if "l" in edges or "r" in edges:
        return "sb_h_double_arrow"
    if "t" in edges or "b" in edges:
        return "sb_v_double_arrow"
    return ""


def point_in_bbox(*, x1: float, y1: float, x2: float, y2: float, cx: float, cy: float) -> bool:
    return x1 <= cx <= x2 and y1 <= cy <= y2


def point_near_bbox(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    cx: float,
    cy: float,
    pad: float,
) -> bool:
    return (x1 - pad) <= cx <= (x2 + pad) and (y1 - pad) <= cy <= (y2 + pad)
