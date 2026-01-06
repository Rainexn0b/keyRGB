from __future__ import annotations

from typing import Dict, Iterable

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2.0)


def _apply_global_factory(*, layout_tweaks: Dict[str, float], base_image_size: tuple[int, int]):
    iw, ih = base_image_size
    px = iw / 2.0
    py = ih / 2.0

    g_dx = float(layout_tweaks.get("dx", 0.0))
    g_dy = float(layout_tweaks.get("dy", 0.0))
    g_sx = float(layout_tweaks.get("sx", 1.0))
    g_sy = float(layout_tweaks.get("sy", 1.0))

    def apply_global(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        x = (x - px) * g_sx + px + g_dx
        y = (y - py) * g_sy + py + g_dy
        return x, y, w * g_sx, h * g_sy

    return apply_global


def _apply_per_key(
    *,
    key_id: str,
    gx: float,
    gy: float,
    gw: float,
    gh: float,
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
) -> tuple[float, float, float, float, float, float, dict[str, float]]:
    kt = dict(per_key_layout_tweaks.get(key_id, {}) or {})
    kdx = float(kt.get("dx", 0.0))
    kdy = float(kt.get("dy", 0.0))
    ksx = float(kt.get("sx", 1.0))
    ksy = float(kt.get("sy", 1.0))

    cx = gx + gw / 2.0
    cy = gy + gh / 2.0
    w2 = gw * ksx
    h2 = gh * ksy
    x2 = cx - (w2 / 2.0) + kdx
    y2 = cy - (h2 / 2.0) + kdy
    cx2 = x2 + w2 / 2.0
    cy2 = y2 + h2 / 2.0
    return x2, y2, w2, h2, cx2, cy2, kt


def _build_items(
    *,
    keys: Iterable[KeyDef],
    apply_global,
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
) -> list[dict]:
    items: list[dict] = []
    for kd in keys:
        x, y, w, h = (float(v) for v in kd.rect)
        gx, gy, gw, gh = apply_global(x, y, w, h)
        x2, y2, w2, h2, cx2, cy2, kt = _apply_per_key(
            key_id=kd.key_id,
            gx=gx,
            gy=gy,
            gw=gw,
            gh=gh,
            per_key_layout_tweaks=per_key_layout_tweaks,
        )
        items.append(
            {
                "key_id": kd.key_id,
                "gx": gx,
                "gy": gy,
                "gw": gw,
                "gh": gh,
                "x": x2,
                "y": y2,
                "w": w2,
                "h": h2,
                "cx": cx2,
                "cy": cy2,
                "kt": kt,
            }
        )
    return items


def _cluster_sorted(vals: list[dict], axis: str, thresh: float) -> list[list[dict]]:
    out: list[list[dict]] = []
    cur: list[dict] = []
    cur_center: float | None = None
    for it in sorted(vals, key=lambda d: float(d[axis])):
        v = float(it[axis])
        if cur_center is None:
            cur = [it]
            cur_center = v
            continue
        if abs(v - cur_center) <= thresh:
            cur.append(it)
            cur_center = float(sum(float(x[axis]) for x in cur) / len(cur))
            continue
        out.append(cur)
        cur = [it]
        cur_center = v
    if cur:
        out.append(cur)
    return out


def _sync_similar_sizes(items: list[dict], *, per_key_layout_tweaks: Dict[str, Dict[str, float]]) -> None:
    size_bins: dict[tuple[int, int], list[dict]] = {}
    for it in items:
        bw = int(round(float(it["w"]) / 6.0))
        bh = int(round(float(it["h"]) / 6.0))
        size_bins.setdefault((bw, bh), []).append(it)

    for _bin, group in size_bins.items():
        if len(group) < 2:
            continue
        ws = [float(it["w"]) for it in group]
        hs = [float(it["h"]) for it in group]
        target_w = _median(ws)
        target_h = _median(hs)

        if (max(ws) - min(ws)) > max(4.0, target_w * 0.08):
            continue
        if (max(hs) - min(hs)) > max(4.0, target_h * 0.08):
            continue

        for it in group:
            key_id = str(it["key_id"])
            gw = max(1e-6, float(it["gw"]))
            gh = max(1e-6, float(it["gh"]))
            kt = dict(per_key_layout_tweaks.get(key_id, {}) or {})
            kt["sx"] = max(0.3, min(4.0, float(target_w) / gw))
            kt["sy"] = max(0.3, min(4.0, float(target_h) / gh))
            per_key_layout_tweaks[key_id] = kt


def _row_and_col_thresholds(items2: list[dict]) -> tuple[float, float]:
    med_w = _median([float(it["gw"]) for it in items2])
    med_h = _median([float(it["gh"]) for it in items2])
    x_thresh = max(2.0, med_w * 0.08)
    y_thresh = max(2.0, med_h * 0.15)
    return x_thresh, y_thresh


def _snap_rows(
    *,
    items2: list[dict],
    y_thresh: float,
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
) -> None:
    for row_group in _cluster_sorted(items2, "cy", y_thresh):
        if len(row_group) < 2:
            continue
        target_cy = _median([float(it["cy"]) for it in row_group])
        for it in row_group:
            key_id = str(it["key_id"])
            cy = float(it["cy"])
            delta = target_cy - cy
            if abs(delta) < 0.25:
                continue
            kt = dict(per_key_layout_tweaks.get(key_id, {}) or {})
            kt["dy"] = float(kt.get("dy", 0.0)) + delta
            per_key_layout_tweaks[key_id] = kt


def _snap_cols(
    *,
    items3: list[dict],
    x_thresh: float,
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
) -> None:
    for col_group in _cluster_sorted(items3, "cx", x_thresh):
        if len(col_group) < 2:
            continue
        target_cx = _median([float(it["cx"]) for it in col_group])
        for it in col_group:
            key_id = str(it["key_id"])
            cx = float(it["cx"])
            delta = target_cx - cx
            if abs(delta) < 0.25:
                continue
            kt = dict(per_key_layout_tweaks.get(key_id, {}) or {})
            kt["dx"] = float(kt.get("dx", 0.0)) + delta
            per_key_layout_tweaks[key_id] = kt


def auto_sync_per_key_overlays(
    *,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    keys: Iterable[KeyDef] = REFERENCE_DEVICE_KEYS,
    base_image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> None:
    """Normalize per-key overlay tweaks after manual adjustments.

    - Keys with very similar sizes are forced to identical sizes.
    - Keys with very similar x/y positions are snapped onto shared columns/rows.

    This mutates `per_key_layout_tweaks` in place.

    Note: This only changes per-key overlay tweaks (dx/dy/sx/sy), not global tweaks.
    """

    apply_global = _apply_global_factory(layout_tweaks=layout_tweaks, base_image_size=base_image_size)
    items = _build_items(keys=keys, apply_global=apply_global, per_key_layout_tweaks=per_key_layout_tweaks)
    if not items:
        return

    _sync_similar_sizes(items, per_key_layout_tweaks=per_key_layout_tweaks)

    items2_full = _build_items(keys=keys, apply_global=apply_global, per_key_layout_tweaks=per_key_layout_tweaks)
    items2 = [
        {
            "key_id": it["key_id"],
            "gw": it["gw"],
            "gh": it["gh"],
            "cx": it["cx"],
            "cy": it["cy"],
        }
        for it in items2_full
    ]
    x_thresh, y_thresh = _row_and_col_thresholds(items2)
    _snap_rows(items2=items2, y_thresh=y_thresh, per_key_layout_tweaks=per_key_layout_tweaks)

    items3_full = _build_items(keys=keys, apply_global=apply_global, per_key_layout_tweaks=per_key_layout_tweaks)
    items3 = [{"key_id": it["key_id"], "cx": it["cx"]} for it in items3_full]
    _snap_cols(items3=items3, x_thresh=x_thresh, per_key_layout_tweaks=per_key_layout_tweaks)
